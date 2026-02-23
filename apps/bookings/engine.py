"""
Booking engine — pure business logic, no HTTP/request awareness.

Public API:
  get_available_slots(worker, service, date)
  get_available_workers_for_slot(branch, service, date, start_time)
  pick_least_booked_worker(workers, date)
  acquire_slot_lock(worker, branch, service, date, start_time, session_key)
  release_slot_lock(lock)
  create_pending_booking(slot_lock, guest, service, notes='')
"""
from datetime import datetime, timedelta, date as date_type, time as time_type
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.workers.models import Worker, WorkerSchedule, WorkerLeave
from apps.bookings.models import Booking, BookingStatus, SlotLock
from apps.bookings.exceptions import (
    SlotConflictError,
    SlotAlreadyLockedException,
    WorkerNotAvailableError,
    NoWorkersAvailableError,
    SameDayCutoffError,
    InvalidSlotError,
)


# ── Time helpers ──────────────────────────────────────────────────────────────

def _add_minutes(t: time_type, minutes: int) -> time_type:
    """Add minutes to a time object."""
    dt = datetime.combine(date_type.today(), t) + timedelta(minutes=minutes)
    return dt.time()


def _fmt_time(t: time_type) -> str:
    """
    Format time as '10:00 AM' without a leading zero on the hour.
    Cross-platform replacement for strftime('%-I:%M %p') which is Linux-only.
    %-I crashes on Windows; %#I crashes on Linux. This is safe on both.
    """
    hour = t.hour % 12 or 12          # convert 0→12, 13→1, etc.
    minute = t.strftime('%M')
    ampm = 'AM' if t.hour < 12 else 'PM'
    return f"{hour}:{minute} {ampm}"


def _time_to_minutes(t: time_type) -> int:
    return t.hour * 60 + t.minute


def _overlaps(a_start: time_type, a_end: time_type,
              b_start: time_type, b_end: time_type) -> bool:
    """True if time window [a_start, a_end) overlaps [b_start, b_end)."""
    return _time_to_minutes(a_start) < _time_to_minutes(b_end) and \
           _time_to_minutes(a_end) > _time_to_minutes(b_start)


# ── Occupied window helpers ───────────────────────────────────────────────────

def _get_occupied_windows(worker: Worker, booking_date: date_type) -> list:
    """
    Returns a list of (start, end) time tuples that are currently occupied
    for the given worker on the given date.

    Includes:
      - CONFIRMED bookings (permanent)
      - Active SlotLocks that are not released and not expired (temporary holds)
    """
    now = timezone.now()
    occupied = []

    # Confirmed bookings
    for b in Booking.objects.filter(
        worker=worker,
        booking_date=booking_date,
        status=BookingStatus.CONFIRMED,
    ):
        occupied.append((b.start_time, b.end_time))

    # Active slot locks (excludes expired, released)
    for lock in SlotLock.objects.filter(
        worker=worker,
        booking_date=booking_date,
        released=False,
        expires_at__gt=now,
    ):
        occupied.append((lock.start_time, lock.end_time))

    return occupied


def _is_same_day_cutoff(booking_date: date_type, start_time: time_type) -> bool:
    """
    Returns True if the slot is too close for a same-day booking.
    Cutoff = SAME_DAY_BOOKING_CUTOFF_HOURS (default 2h) before slot start.
    """
    now_local = timezone.localtime(timezone.now())
    if booking_date != now_local.date():
        return False
    cutoff = (datetime.combine(booking_date, start_time)
              - timedelta(hours=settings.SAME_DAY_BOOKING_CUTOFF_HOURS))
    return datetime.combine(booking_date, now_local.time()) > cutoff


# ── Core: Availability Engine ──────────────────────────────────────────────────

def get_availability_window(branch, worker, booking_date: date_type):
    """
    Centralized source of truth for availability.
    Returns (start_time, end_time) tuple or None if unavailable.
    """
    weekday = booking_date.weekday()

    # 1. Branch working days check
    if weekday not in branch.get_working_days():
        # print(f"DEBUG: Branch {branch.name} closed on weekday {weekday}")
        return None

    # 2. Worker active check
    if not worker.is_active:
        return None

    # 3. Worker leave check
    if WorkerLeave.objects.filter(worker=worker, leave_date=booking_date).exists():
        return None

    # 4. Determine Window (Strict Branch-Only)
    # Individual WorkerSchedules are ignored per business requirements.
    # All active workers are available for the full duration of branch hours.
    start = branch.opening_time
    end   = branch.closing_time

    # 5. Safety check
    if _time_to_minutes(start) >= _time_to_minutes(end):
        return None

    # print(f"DEBUG: Availability for {worker.name} on {booking_date}: {start} - {end}")
    return start, end


# ── Core: Slot Generation ─────────────────────────────────────────────────────

def get_available_slots(worker: Worker, service, booking_date: date_type) -> list:
    """
    Generate all available booking slots for a worker+service+date.

    Returns a list of dicts:
      [{"start": time, "end": time, "display": "10:00 AM – 11:00 AM"}, ...]

    Empty list means no availability (off day, on leave, fully booked).
    """
    # Worker must not be soft-deleted
    if not worker.is_active:
        return []

    window = get_availability_window(worker.branch, worker, booking_date)
    if not window:
        return []

    window_start, window_end = window

    # Cannot book past dates
    now_local = timezone.localtime(timezone.now())
    if booking_date < now_local.date():
        return []

    total_block = service.duration_minutes + service.buffer_minutes
    occupied = _get_occupied_windows(worker, booking_date)

    slots = []
    current = window_start

    while True:
        slot_end = _add_minutes(current, service.duration_minutes)    # visible end
        block_end = _add_minutes(current, total_block)               # internal end (incl. buffer)

        if _time_to_minutes(block_end) > _time_to_minutes(window_end):
            break  # No room for another slot

        # Skip same-day slots within the cutoff window
        if _is_same_day_cutoff(booking_date, current):
            current = _add_minutes(current, total_block)
            continue

        # Skip if overlaps any occupied window
        if not any(_overlaps(current, block_end, occ_s, occ_e) for occ_s, occ_e in occupied):
            slots.append({
                "start": current,
                "end": slot_end,
                "display": f"{_fmt_time(current)} – {_fmt_time(slot_end)}",
                "start_str": current.strftime("%H:%M"),
                "end_str": slot_end.strftime("%H:%M"),
            })

        current = _add_minutes(current, total_block)

    return slots


# ── Core: "Any Worker" Support ────────────────────────────────────────────────

def get_available_workers_for_slot(branch, service, booking_date: date_type,
                                   start_time: time_type) -> list:
    """
    Returns the list of Worker objects available for the exact given slot
    at the given branch+service+date+start_time.

    Used when guest selects "Any Available" to build the candidate pool.
    """
    block_end = _add_minutes(start_time, service.duration_minutes + service.buffer_minutes)
    now = timezone.now()
    candidates = []

    for worker in Worker.objects.filter(branch=branch, is_active=True):
        window = get_availability_window(branch, worker, booking_date)
        if not window:
            continue

        window_start, window_end = window

        if (_time_to_minutes(start_time) < _time_to_minutes(window_start) or
                _time_to_minutes(block_end) > _time_to_minutes(window_end)):
            continue

        # Must not have an overlap in occupied windows
        occupied = _get_occupied_windows(worker, booking_date)
        if any(_overlaps(start_time, block_end, occ_s, occ_e) for occ_s, occ_e in occupied):
            continue

        candidates.append(worker)

    return candidates


def pick_least_booked_worker(workers: list, booking_date: date_type) -> Worker:
    """
    From a list of available workers, pick the one with the fewest
    CONFIRMED bookings on booking_date (fairness distribution).
    Tie-break: lowest UUID string (deterministic).

    Raises NoWorkersAvailableError if workers list is empty.
    """
    if not workers:
        raise NoWorkersAvailableError("No workers available for the selected slot.")

    confirmed_counts = {
        w: Booking.objects.filter(
            worker=w, booking_date=booking_date, status=BookingStatus.CONFIRMED
        ).count()
        for w in workers
    }
    return min(workers, key=lambda w: (confirmed_counts[w], str(w.id)))


# ── Core: Atomic Slot Lock ────────────────────────────────────────────────────

@transaction.atomic
def acquire_slot_lock(worker: Worker, branch, service, booking_date: date_type,
                      start_time: time_type, session_key: str) -> SlotLock:
    """
    Atomically acquires a SlotLock for worker+date+start_time.

    Steps (all inside a single transaction with SELECT FOR UPDATE):
      1. Check no CONFIRMED booking already exists at this slot
      2. Check no active (non-expired) SlotLock exists at this slot
      3. Create and return a new SlotLock (TTL = SLOT_LOCK_TTL_MINUTES)

    Raises:
      SlotConflictError        — CONFIRMED booking already holds this slot
      SlotAlreadyLockedException — active lock holds this slot
      SameDayCutoffError       — slot is within the same-day cutoff window
      InvalidSlotError         — start_time is outside worker's scheduled hours
    """
    # Re-validate same-day cutoff inside the transaction too
    if _is_same_day_cutoff(booking_date, start_time):
        raise SameDayCutoffError(
            "This slot is too close to the current time. "
            "Please choose a slot at least 2 hours from now."
        )

    block_end = _add_minutes(start_time, service.duration_minutes + service.buffer_minutes)

    # 1. Lock rows and check for existing confirmed booking
    existing_booking = (
        Booking.objects
        .select_for_update()
        .filter(
            worker=worker,
            booking_date=booking_date,
            start_time=start_time,
            status=BookingStatus.CONFIRMED,
        )
        .first()
    )
    if existing_booking:
        raise SlotConflictError(
            "This slot was just confirmed by another customer. Please choose a different time."
        )

    now = timezone.now()

    # 2. Check for active slot lock
    existing_lock = (
        SlotLock.objects
        .select_for_update()
        .filter(
            worker=worker,
            booking_date=booking_date,
            start_time=start_time,
            released=False,
            expires_at__gt=now,
        )
        .first()
    )
    if existing_lock:
        raise SlotAlreadyLockedException(
            "This slot is being held by another customer completing their payment. "
            "Please choose a different time or try again shortly."
        )

    # 3. Create lock
    ttl_minutes = getattr(settings, 'SLOT_LOCK_TTL_MINUTES', 10)
    lock = SlotLock.objects.create(
        worker=worker,
        branch=branch,
        booking_date=booking_date,
        start_time=start_time,
        end_time=block_end,
        session_key=session_key,
        expires_at=now + timedelta(minutes=ttl_minutes),
        released=False,
    )
    return lock


def release_slot_lock(lock: SlotLock) -> None:
    """Explicitly release a slot lock (e.g., user goes back to change slot)."""
    lock.released = True
    lock.save(update_fields=['released'])


# ── Core: Booking Creation ────────────────────────────────────────────────────

def create_pending_booking(slot_lock: SlotLock, guest, service, notes: str = '') -> Booking:
    """
    Create a Booking in PENDING_PAYMENT state from a confirmed SlotLock.
    Amount is snapshot from service.price at time of booking (immutable receipt).
    """
    booking = Booking.objects.create(
        branch=slot_lock.branch,
        service=service,
        worker=slot_lock.worker,
        guest=guest,
        slot_lock=slot_lock,
        booking_date=slot_lock.booking_date,
        start_time=slot_lock.start_time,
        end_time=_add_minutes(slot_lock.start_time, service.duration_minutes),
        duration_minutes=service.duration_minutes,
        status=BookingStatus.PENDING_PAYMENT,
        payment_status='PENDING',
        amount_paid=service.price,   # price snapshot
        notes=notes,
        is_manual=False,
    )
    return booking


def create_manual_booking(branch, service, worker, guest, booking_date: date_type,
                           start_time: time_type, notes: str = '', changed_by: str = 'admin') -> Booking:
    """
    Admin-created booking. Bypasses slot lock and payment.
    Creates directly as CONFIRMED with payment_status=WAIVED.

    Raises SlotConflictError if slot is already confirmed.
    """
    # Validate no conflict even for admin bookings
    existing = Booking.objects.filter(
        worker=worker,
        booking_date=booking_date,
        start_time=start_time,
        status=BookingStatus.CONFIRMED,
    ).first()
    if existing:
        raise SlotConflictError(
            f"Worker {worker.name} already has a confirmed booking at this time."
        )

    booking = Booking.objects.create(
        branch=branch,
        service=service,
        worker=worker,
        guest=guest,
        booking_date=booking_date,
        start_time=start_time,
        end_time=_add_minutes(start_time, service.duration_minutes),
        duration_minutes=service.duration_minutes,
        status=BookingStatus.CONFIRMED,
        payment_status='WAIVED',
        amount_paid=0,
        notes=notes,
        is_manual=True,
    )
    # Log the creation
    from apps.bookings.models import BookingStatusLog, BookingStatus as BS
    BookingStatusLog.objects.create(
        booking=booking,
        from_status='',
        to_status=BS.CONFIRMED,
        changed_by=changed_by,
        reason='Manual booking created by admin',
    )
    return booking
