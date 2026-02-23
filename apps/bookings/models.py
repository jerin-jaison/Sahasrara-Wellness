"""
Bookings app models:
  - SlotLock   : Atomic TTL-based slot reservation (pre-payment)
  - Booking    : Core booking record with state machine
  - BookingStatusLog : Full audit trail of state transitions
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from apps.core.models import BaseModel, UUIDModel, TimestampedModel
from apps.branches.models import Branch
from apps.services.models import Service
from apps.workers.models import Worker
from apps.guests.models import Guest


# ── Slot Lock ─────────────────────────────────────────────────────────────────

class SlotLock(UUIDModel, TimestampedModel):
    """
    Atomic, TTL-based slot reservation acquired BEFORE payment.
    Prevents two guests from booking the same worker slot simultaneously.
    Released when:
      - Payment confirmed (lock kept — slot is now a confirmed booking)
      - TTL expired (lock released by cleanup cron)
    """
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='slot_locks')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='slot_locks')
    booking_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    session_key = models.CharField(max_length=40, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    released = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = 'Slot Lock'
        verbose_name_plural = 'Slot Locks'
        # Prevent two active locks for the same worker+date+time
        constraints = [
            models.UniqueConstraint(
                fields=['worker', 'booking_date', 'start_time'],
                condition=models.Q(released=False),
                name='uq_active_slot_lock',
            )
        ]

    def __str__(self):
        return (
            f"Lock: {self.worker.name} on {self.booking_date} "
            f"at {self.start_time} [{'released' if self.released else 'active'}]"
        )

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_active(self):
        return not self.released and not self.is_expired


# ── Booking State Machine ─────────────────────────────────────────────────────

class BookingStatus(models.TextChoices):
    PENDING_PAYMENT = 'PENDING_PAYMENT', 'Pending Payment'
    CONFIRMED       = 'CONFIRMED',       'Confirmed'
    COMPLETED       = 'COMPLETED',       'Completed'
    CANCELLED       = 'CANCELLED',       'Cancelled'
    EXPIRED         = 'EXPIRED',         'Expired'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PAID    = 'PAID',    'Paid'
    WAIVED  = 'WAIVED',  'Waived (Admin)'
    FAILED  = 'FAILED',  'Failed'


class Booking(BaseModel):
    """
    Core booking record. Created when guest completes Step 7 (review).
    Status transitions controlled by explicit methods — not direct field writes.
    """
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='bookings')
    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name='bookings')
    guest = models.ForeignKey(Guest, on_delete=models.PROTECT, related_name='bookings')
    slot_lock = models.OneToOneField(
        SlotLock, on_delete=models.SET_NULL, null=True, blank=True, related_name='booking',
    )

    booking_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(
        help_text='Actual booked duration (service.duration_minutes at time of booking)',
    )

    status = models.CharField(
        max_length=20, choices=BookingStatus.choices,
        default=BookingStatus.PENDING_PAYMENT, db_index=True,
    )
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )

    # Secure access token for guest inbox (emailed, no login required)
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    notes = models.TextField(blank=True)
    is_manual = models.BooleanField(
        default=False,
        help_text='True if created by admin on behalf of customer (payment waived)',
    )

    class Meta:
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-booking_date', '-start_time']
        # DB-level guard: no two CONFIRMED bookings for same worker+date+time
        constraints = [
            models.UniqueConstraint(
                fields=['worker', 'booking_date', 'start_time'],
                condition=models.Q(status='CONFIRMED'),
                name='uq_confirmed_booking_slot',
            )
        ]

    def __str__(self):
        return (
            f"#{self.id_short} | {self.guest.name} | "
            f"{self.service.name} | {self.booking_date} {self.start_time}"
        )

    @property
    def id_short(self):
        """Returns the first 8 chars of UUID in uppercase."""
        return str(self.id)[:8].upper()

    @property
    def status_badge_class(self):
        """CSS class for status badge."""
        classes = {
            'CONFIRMED': 'badge-confirmed',
            'COMPLETED': 'badge-completed',
            'CANCELLED': 'badge-cancelled',
            'PENDING_PAYMENT': 'badge-pending',
            'EXPIRED': 'badge-expired',
        }
        return classes.get(self.status, 'badge-expired')

    @property
    def payment_badge_class(self):
        """CSS class for payment status badge."""
        classes = {
            'PAID': 'badge-confirmed',
            'WAIVED': 'badge-completed',
            'FAILED': 'badge-cancelled',
            'PENDING': 'badge-pending',
        }
        return classes.get(self.payment_status, 'badge-pending')

    # ── State transition helpers ──────────────────────────────────────────────

    def confirm(self, changed_by='system'):
        """Transition to CONFIRMED after payment verified."""
        self._transition(BookingStatus.CONFIRMED, changed_by)
        self.payment_status = PaymentStatus.PAID
        self.save(update_fields=['status', 'payment_status', 'updated_at'])

    def complete(self, changed_by='admin'):
        """Mark service as delivered."""
        self._transition(BookingStatus.COMPLETED, changed_by)
        self.save(update_fields=['status', 'updated_at'])

    def cancel(self, changed_by='admin', reason=''):
        """Emergency cancel by admin."""
        self._transition(BookingStatus.CANCELLED, changed_by, reason)
        self.save(update_fields=['status', 'updated_at'])

    def expire(self, changed_by='system'):
        """Slot lock TTL elapsed without payment."""
        self._transition(BookingStatus.EXPIRED, changed_by)
        self.save(update_fields=['status', 'updated_at'])

    def _transition(self, new_status, changed_by, reason=''):
        old_status = self.status
        self.status = new_status
        BookingStatusLog.objects.create(
            booking=self,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )


# ── Booking Audit Log ─────────────────────────────────────────────────────────

class BookingStatusLog(UUIDModel):
    """Immutable audit trail of every status transition on a booking."""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='status_logs')
    from_status = models.CharField(max_length=20, choices=BookingStatus.choices)
    to_status = models.CharField(max_length=20, choices=BookingStatus.choices)
    changed_by = models.CharField(max_length=80, help_text='system / admin / webhook')
    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Booking Status Log'
        verbose_name_plural = 'Booking Status Logs'
        ordering = ['changed_at']

    def __str__(self):
        return f"Booking {str(self.booking_id)[:8]}: {self.from_status} → {self.to_status}"
