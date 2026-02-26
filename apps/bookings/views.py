"""
Booking flow views — 7-step multi-page form backed by Django sessions.

Each view guards that required previous steps are complete before rendering.
AJAX endpoints return JSON for slot grid and worker availability.
"""
import json
import logging
from datetime import date as date_type, datetime

from django.contrib import messages
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.branches.models import Branch
from apps.guests.models import Guest
from apps.services.models import Service
from apps.workers.models import Worker
from apps.notifications.emails import send_booking_confirmed
from apps.dashboard.forms import WEEKDAY_CHOICES

from .engine import (
    create_pending_booking,
    acquire_slot_lock,
    get_available_slots,
    get_available_workers_for_slot,
    pick_least_booked_worker,
    get_availability_window,
    release_slot_lock,
)
from .exceptions import (
    BookingEngineError,
    SlotConflictError,
    SlotAlreadyLockedException,
    SameDayCutoffError,
    NoWorkersAvailableError,
)
from .forms import GuestInfoForm, PhoneLookupForm
from .models import Booking, BookingStatus, SlotLock
from .session import (
    get_booking_session,
    set_booking_session,
    clear_booking_session,
    booking_session_get,
    step_is_complete,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _get_session_objects(request):
    """Load Branch, Service, Worker from session IDs. Returns dict or None on missing."""
    s = get_booking_session(request)
    try:
        branch = Branch.objects.get(id=s.get('branch_id'), is_active=True)
        service = Service.objects.get(id=s.get('service_id'), is_active=True)
    except (Branch.DoesNotExist, Service.DoesNotExist):
        return None

    worker = None
    worker_id = s.get('worker_id')
    if worker_id and worker_id != 'any':
        try:
            worker = Worker.objects.get(id=worker_id, is_active=True)
        except Worker.DoesNotExist:
            return None

    return {'branch': branch, 'service': service, 'worker': worker, 'worker_id': worker_id}


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Branch Selection
# ─────────────────────────────────────────────────────────────────────────────

def step1_branch(request):
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        if not branch_id or not Branch.objects.filter(id=branch_id, is_active=True).exists():
            messages.error(request, 'Please select a valid branch.')
            return redirect('bookings:step1_branch')

        # New branch selection — clear previous booking session to start fresh
        clear_booking_session(request)
        set_booking_session(request, {'branch_id': branch_id})
        return redirect('bookings:step2_services')

    branches = Branch.objects.filter(is_active=True).order_by('name')
    return render(request, 'bookings/step1_branch.html', {'branches': branches})


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Service Selection
# ─────────────────────────────────────────────────────────────────────────────

def step2_services(request):
    if not step_is_complete(request, 1):
        return redirect('bookings:step1_branch')

    branch_id = booking_session_get(request, 'branch_id')
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    services = Service.objects.filter(branches=branch, is_active=True).order_by('name', 'duration_minutes')

    if request.method == 'POST':
        service_id = request.POST.get('service_id')
        if not services.filter(id=service_id).exists():
            messages.error(request, 'Please select a valid service.')
            return redirect('bookings:step2_services')

        set_booking_session(request, {'service_id': service_id})
        return redirect('bookings:step3_workers')

    return render(request, 'bookings/step2_services.html', {
        'branch': branch,
        'services': services,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Worker Selection
# ─────────────────────────────────────────────────────────────────────────────

def step3_workers(request):
    if not step_is_complete(request, 2):
        return redirect('bookings:step2_services')

    objs = _get_session_objects(request)
    if not objs:
        return redirect('bookings:step1_branch')

    branch, service = objs['branch'], objs['service']
    workers = Worker.objects.filter(branch=branch, is_active=True).order_by('name')

    if request.method == 'POST':
        worker_id = request.POST.get('worker_id')  # UUID or 'any'
        if worker_id != 'any' and not workers.filter(id=worker_id).exists():
            messages.error(request, 'Please select a valid worker or choose Any Available.')
            return redirect('bookings:step3_workers')

        set_booking_session(request, {'worker_id': worker_id})
        return redirect('bookings:step4_date')

    return render(request, 'bookings/step3_workers.html', {
        'branch': branch,
        'service': service,
        'workers': workers,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Date Selection
# ─────────────────────────────────────────────────────────────────────────────

def step4_date(request):
    if not step_is_complete(request, 3):
        return redirect('bookings:step3_workers')

    objs = _get_session_objects(request)
    if not objs:
        return redirect('bookings:step1_branch')

    branch, service = objs['branch'], objs['service']
    today = timezone.localtime(timezone.now()).date()

    if request.method == 'POST':
        date_str = request.POST.get('booking_date')
        booking_date = _parse_date(date_str)
        if not booking_date or booking_date < today:
            messages.error(request, 'Please choose a valid future date.')
            return redirect('bookings:step4_date')

        set_booking_session(request, {'booking_date': date_str})
        return redirect('bookings:step5_slots')

    # Pre-process working days for display (optional but helpful)
    days_map = dict(WEEKDAY_CHOICES)
    allowed_days = branch.get_working_days()
    working_days_display = ", ".join([str(days_map.get(str(d))) for d in allowed_days])

    return render(request, 'bookings/step4_date.html', {
        'branch': branch,
        'service': service,
        'today': today.isoformat(),
        'working_days_display': working_days_display,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Slot Selection
# ─────────────────────────────────────────────────────────────────────────────

def step5_slots(request):
    if not step_is_complete(request, 4):
        return redirect('bookings:step4_date')

    objs = _get_session_objects(request)
    if not objs:
        return redirect('bookings:step1_branch')

    branch, service = objs['branch'], objs['service']
    worker, worker_id = objs['worker'], objs['worker_id']

    date_str = booking_session_get(request, 'booking_date')
    booking_date = _parse_date(date_str)
    if not booking_date:
        return redirect('bookings:step4_date')

    if request.method == 'POST':
        start_time_str = request.POST.get('start_time')
        if not start_time_str:
            messages.error(request, 'Please select a time slot.')
            return redirect('bookings:step5_slots')

        set_booking_session(request, {'start_time': start_time_str})
        return redirect('bookings:step6_info')

    # Render: if specific worker, show their slots. If 'any', show union of all slots.
    if worker_id == 'any':
        all_workers = Worker.objects.filter(branch=branch, is_active=True)
        slots_set = {}
        is_branch_open = False
        
        for w in all_workers:
            # Sync is_branch_open: if any worker has a window, we consider it "open"
            if get_availability_window(branch, w, booking_date):
                is_branch_open = True
                
            for slot in get_available_slots(w, service, booking_date):
                key = slot['start_str']
                if key not in slots_set:
                    slots_set[key] = slot
        slots = sorted(slots_set.values(), key=lambda s: s['start_str'])
    else:
        # Specific worker: derive is_branch_open from their window
        window = get_availability_window(branch, worker, booking_date)
        is_branch_open = window is not None
        slots = get_available_slots(worker, service, booking_date)

    # DEBUG (Temporary as requested)
    # print(f"DEBUG: is_branch_open={is_branch_open}, slots_count={len(slots)}")

    return render(request, 'bookings/step5_slots.html', {
        'branch':       branch,
        'service':      service,
        'worker':       worker,
        'worker_id':    worker_id,
        'booking_date': booking_date,
        'slots':        slots,
        'is_branch_open': is_branch_open,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Guest Information
# ─────────────────────────────────────────────────────────────────────────────

def step6_info(request):
    if not step_is_complete(request, 5):
        return redirect('bookings:step5_slots')

    objs = _get_session_objects(request)
    if not objs:
        return redirect('bookings:step1_branch')

    # Pre-fill form from session if guest already entered info
    s = get_booking_session(request)
    initial = {
        'name': s.get('guest_name', ''),
        'phone': s.get('guest_phone', ''),
        'email': s.get('guest_email', ''),
        'notes': s.get('notes', ''),
    }

    if request.method == 'POST':
        form = GuestInfoForm(request.POST)
        if form.is_valid():
            set_booking_session(request, {
                'guest_name':  form.cleaned_data['name'],
                'guest_phone': form.cleaned_data['phone'],
                'guest_email': form.cleaned_data.get('email', ''),
                'notes':       form.cleaned_data.get('notes', ''),
            })
            return redirect('bookings:step7_review')
    else:
        form = GuestInfoForm(initial=initial)

    service = objs['service']
    return render(request, 'bookings/step6_info.html', {
        'form': form,
        'service': objs['service'],
        'branch': objs['branch'],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Review & Lock Slot
# ─────────────────────────────────────────────────────────────────────────────

def step7_review(request):
    if not step_is_complete(request, 6):
        return redirect('bookings:step6_info')

    objs = _get_session_objects(request)
    if not objs:
        return redirect('bookings:step1_branch')

    s = get_booking_session(request)
    branch, service = objs['branch'], objs['service']
    worker, worker_id = objs['worker'], objs['worker_id']
    booking_date = _parse_date(s.get('booking_date'))
    start_time_str = s.get('start_time')

    try:
        from datetime import datetime
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return redirect('bookings:step5_slots')

    if request.method == 'POST':
        # ── Handle Payment Type Selection ─────────────────────────────────────
        payment_type = request.POST.get('payment_type', 'deposit')  # 'deposit' or 'full'
        set_booking_session(request, {'payment_type': payment_type})

        # ── Resolve "Any Worker" to actual worker ─────────────────────────────
        if worker_id == 'any':
            candidates = get_available_workers_for_slot(branch, service, booking_date, start_time)
            try:
                worker = pick_least_booked_worker(candidates, booking_date)
            except NoWorkersAvailableError:
                messages.error(
                    request,
                    'No workers are available for this slot anymore. Please choose another time.',
                )
                set_booking_session(request, {'start_time': None})
                return redirect('bookings:step5_slots')
            # Save the resolved worker back to session
            set_booking_session(request, {'worker_id': str(worker.id)})

        # ── Acquire slot lock ─────────────────────────────────────────────────
        try:
            lock = acquire_slot_lock(
                worker=worker,
                branch=branch,
                service=service,
                booking_date=booking_date,
                start_time=start_time,
                session_key=request.session.session_key or '',
            )
        except SlotConflictError as exc:
            messages.error(request, str(exc))
            return redirect('bookings:step5_slots')
        except SlotAlreadyLockedException as exc:
            messages.error(request, str(exc))
            return redirect('bookings:step5_slots')
        except SameDayCutoffError as exc:
            messages.error(request, str(exc))
            return redirect('bookings:step5_slots')
        except BookingEngineError as exc:
            messages.error(request, str(exc))
            return redirect('bookings:step5_slots')

        # ── Get/create guest ──────────────────────────────────────────────────
        guest, _ = Guest.get_or_create_by_phone(
            name=s.get('guest_name'),
            phone=s.get('guest_phone'),
            email=s.get('guest_email', ''),
        )

        # ── Create PENDING_PAYMENT booking ────────────────────────────────────
        try:
            booking = create_pending_booking(
                slot_lock=lock,
                guest=guest,
                service=service,
                notes=s.get('notes', ''),
            )
        except Exception as exc:
            logger.exception('Failed to create pending booking')
            release_slot_lock(lock)
            messages.error(request, 'Could not create booking. Please try again.')
            return redirect('bookings:step7_review')

        set_booking_session(request, {
            'slot_lock_id': str(lock.id),
            'booking_id': str(booking.id),
        })

        # ── Redirect to Razorpay payment page ────────────────────────────────
        return redirect('payments:initiate', booking_id=booking.id)

    # GET: Show review summary
    return render(request, 'bookings/step7_review.html', {
        'branch': branch,
        'service': service,
        'worker': worker,
        'worker_is_any': worker_id == 'any',
        'booking_date': booking_date,
        'start_time': start_time,
        'guest_name': s.get('guest_name'),
        'guest_phone': s.get('guest_phone'),
        'guest_email': s.get('guest_email'),
        'notes': s.get('notes'),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Booking Confirmation Page
# ─────────────────────────────────────────────────────────────────────────────

def booking_confirmation(request, booking_id):
    """
    Final confirmation page after successful payment.
    Supports session-less access via token.
    """
    token = request.GET.get('token')
    
    if token:
        booking = get_object_or_404(
            Booking.objects.select_related('service', 'worker', 'branch', 'guest'),
            id=booking_id,
            access_token=token
        )
    else:
        booking = get_object_or_404(
            Booking.objects.select_related('service', 'worker', 'branch', 'guest'),
            id=booking_id
        )
        # Fallback to session check
        inbox = request.session.get('booking_inbox', [])
        if str(booking.id) not in inbox:
            return redirect('bookings:inbox')

    # Add this booking ID to the session inbox (if session exists)
    if request.session:
        inbox = request.session.get('booking_inbox', [])
        bid = str(booking.id)
        if bid not in inbox:
            inbox.append(bid)
        request.session['booking_inbox'] = inbox
        request.session.modified = True

        # Send confirmation email once (guard against resend on page refresh)
        emailed_set = request.session.get('_confirmed_emails_sent', [])
        if bid not in emailed_set:
            send_booking_confirmed(booking)
            emailed_set.append(bid)
            request.session['_confirmed_emails_sent'] = emailed_set
            request.session.modified = True

        # Clear the booking flow session (start fresh for next booking)
        clear_booking_session(request)

    return render(request, 'bookings/confirmation.html', {'booking': booking})


# ─────────────────────────────────────────────────────────────────────────────
# AJAX: Available Slots
# ─────────────────────────────────────────────────────────────────────────────

@require_GET
def api_slots(request):
    """
    GET /bookings/api/slots/?worker_id=<uuid>&service_id=<uuid>&date=YYYY-MM-DD
    Returns JSON list of available slots.
    """
    worker_id = request.GET.get('worker_id')
    service_id = request.GET.get('service_id')
    date_str = request.GET.get('date')

    booking_date = _parse_date(date_str)
    if not booking_date:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    try:
        service = Service.objects.get(id=service_id, is_active=True)
    except Service.DoesNotExist:
        return JsonResponse({'error': 'Service not found'}, status=404)

    if worker_id == 'any':
        # Return union of all workers' available slots
        branch_id = request.GET.get('branch_id')
        try:
            branch = Branch.objects.get(id=branch_id, is_active=True)
        except Branch.DoesNotExist:
            return JsonResponse({'error': 'Branch not found'}, status=404)

        all_workers = Worker.objects.filter(branch=branch, is_active=True)
        slots_set = {}
        for w in all_workers:
            for slot in get_available_slots(w, service, booking_date):
                key = slot['start_str']
                if key not in slots_set:
                    slots_set[key] = {
                        'start': slot['start_str'],
                        'end': slot['end_str'],
                        'display': slot['display'],
                    }
        slots = sorted(slots_set.values(), key=lambda s: s['start'])
    else:
        try:
            worker = Worker.objects.get(id=worker_id, is_active=True)
        except Worker.DoesNotExist:
            return JsonResponse({'error': 'Worker not found'}, status=404)

        slots = [
            {'start': s['start_str'], 'end': s['end_str'], 'display': s['display']}
            for s in get_available_slots(worker, service, booking_date)
        ]

    return JsonResponse({'slots': slots, 'date': date_str})


@require_GET
def api_available_workers(request):
    """
    GET /book/api/workers/?branch_id=<uuid>&service_id=<uuid>&date=YYYY-MM-DD&start=HH:MM
    Returns list of workers available for a specific slot (for any-worker display).
    """
    from datetime import datetime
    branch_id = request.GET.get('branch_id')
    service_id = request.GET.get('service_id')
    date_str = request.GET.get('date')
    start_str = request.GET.get('start')

    booking_date = _parse_date(date_str)
    if not booking_date or not start_str:
        return JsonResponse({'error': 'Invalid parameters'}, status=400)

    try:
        branch = Branch.objects.get(id=branch_id, is_active=True)
        service = Service.objects.get(id=service_id, is_active=True)
        start_time = datetime.strptime(start_str, '%H:%M').time()
    except (Branch.DoesNotExist, Service.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Invalid parameters'}, status=400)

    workers = get_available_workers_for_slot(branch, service, booking_date, start_time)
    return JsonResponse({
        'workers': [{'id': str(w.id), 'name': w.name} for w in workers],
        'count': len(workers),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Guest Inbox
# ─────────────────────────────────────────────────────────────────────────────

def guest_inbox(request):
    """
    Shows guest's bookings.
    Retrieval strategy (Priority per Requirement 5):
      1. Active session 'booking_inbox' (highest convenience)
      2. Explicit access_token in URL (secure direct link)
      3. Phone number lookup (manual fallback)
    """
    bookings = []
    form = PhoneLookupForm()
    token = request.GET.get('token')

    # 1. Session lookup
    inbox_ids = request.session.get('booking_inbox', [])
    if inbox_ids:
        bookings = (
            Booking.objects
            .filter(id__in=inbox_ids)
            .select_related('service', 'worker', 'branch')
            .order_by('-booking_date', '-start_time')
        )

    # 2. Token-based lookup (if not found in session)
    if not bookings and token:
        bookings = Booking.objects.filter(access_token=token).select_related('service', 'worker', 'branch')
        if not bookings:
             messages.warning(request, "Invalid or expired access token.")

    # 3. Phone lookup (POST - manual fallback)
    if request.method == 'POST':
        form = PhoneLookupForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            try:
                guest = Guest.objects.get(phone=phone)
                lookup_bookings = (
                    Booking.objects
                    .filter(guest=guest)
                    .select_related('service', 'worker', 'branch')
                    .order_by('-booking_date', '-start_time')[:20]
                )
                if lookup_bookings:
                    bookings = lookup_bookings
                else:
                    messages.info(request, 'No bookings found for that mobile number.')
            except Guest.DoesNotExist:
                messages.info(request, 'No records found for that mobile number.')

    return render(request, 'bookings/inbox.html', {
        'bookings': bookings,
        'form': form,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Token-based Booking Detail (from email link)
# ─────────────────────────────────────────────────────────────────────────────

def booking_detail_token(request, access_token):
    booking = get_object_or_404(
        Booking.objects.select_related('service', 'worker', 'branch', 'guest'),
        access_token=access_token,
    )
    return render(request, 'bookings/booking_detail.html', {'booking': booking})


# ─────────────────────────────────────────────────────────────────────────────
# Cancel Lock (Go Back & Change Slot)
# ─────────────────────────────────────────────────────────────────────────────

def cancel_lock(request):
    lock_id = booking_session_get(request, 'slot_lock_id')
    if lock_id:
        try:
            lock = SlotLock.objects.get(id=lock_id)
            release_slot_lock(lock)
        except SlotLock.DoesNotExist:
            pass
        set_booking_session(request, {'slot_lock_id': None, 'booking_id': None})
    return redirect('bookings:step5_slots')
