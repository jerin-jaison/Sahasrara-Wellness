"""
Payment model — records Razorpay payment lifecycle.
One Payment per Booking.

Null-safety note on unique fields:
  PostgreSQL UNIQUE constraints treat every NULL as distinct, so multiple rows
  with NULL in a UNIQUE column are allowed. Django honours this when
  null=True is set alongside unique=True.

  However, to make the intent explicit and avoid Django's system-check
  warning (models.W003), we define these as conditional UniqueConstraints
  in Meta.constraints instead of field-level unique=True.
"""
from django.db import models
from apps.core.models import UUIDModel, TimestampedModel
from apps.bookings.models import Booking


class PaymentStatus(models.TextChoices):
    CREATED   = 'CREATED',   'Created'
    CAPTURED  = 'CAPTURED',  'Captured'
    FAILED    = 'FAILED',    'Failed'
    REFUNDED  = 'REFUNDED',  'Refunded'


class Payment(UUIDModel, TimestampedModel):
    """
    Full Razorpay payment record.
    Created when Razorpay order is created (before payment).
    Updated via webhook when payment is captured.
    """
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name='payment',
    )
    razorpay_order_id = models.CharField(max_length=100, db_index=True)
    # nullable because it is only populated after Razorpay confirms the payment
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.CREATED,
    )
    # FIX 3: nullable, populated only when webhook delivers the event ID.
    # Uniqueness enforced via conditional constraint below (NULL-safe).
    webhook_event_id = models.CharField(max_length=100, blank=True, null=True)
    webhook_payload = models.JSONField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True, help_text='When our webhook completed confirmation.')

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
        constraints = [
            # Enforce uniqueness only on non-NULL values.
            # PostgreSQL partial indexes skip NULLs, preventing false conflicts
            # when the field has not yet been populated.
            models.UniqueConstraint(
                fields=['razorpay_order_id'],
                name='uq_payment_razorpay_order_id',
            ),
            models.UniqueConstraint(
                fields=['razorpay_payment_id'],
                condition=models.Q(razorpay_payment_id__isnull=False),
                name='uq_payment_razorpay_payment_id',
            ),
            models.UniqueConstraint(
                fields=['webhook_event_id'],
                condition=models.Q(webhook_event_id__isnull=False),
                name='uq_payment_webhook_event_id',
            ),
        ]

    def __str__(self):
        return f"Payment {self.razorpay_order_id} [{self.status}] — ₹{self.amount}"
