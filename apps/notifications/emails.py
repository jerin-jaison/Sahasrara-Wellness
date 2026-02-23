"""
Email notification service for Sahasrara Wellness.

All functions are synchronous (no Celery at MVP).
Called directly from views/webhooks after state transitions.

Public API:
  send_booking_confirmed(booking)
  send_booking_cancelled(booking, reason='')
  send_booking_reassigned(booking, old_worker_name)
"""
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def _booking_context(booking) -> dict:
    """Common template context for all booking emails."""
    return {
        'guest_name':    booking.guest.name,
        'service_name':  booking.service.name,
        'worker_name':   booking.worker.name,
        'branch_name':   booking.branch.name,
        'branch_address': getattr(booking.branch, 'address', ''),
        'branch_phone':  getattr(booking.branch, 'phone', ''),
        'booking_date':  booking.booking_date,
        'start_time':    booking.start_time,
        'end_time':      booking.end_time,
        'duration':      booking.duration_minutes,
        'amount_paid':   booking.amount_paid,
        'booking_ref':   str(booking.id)[:8].upper(),
        'access_url':    _access_url(booking),
        'support_email': settings.DEFAULT_FROM_EMAIL,
    }


def _access_url(booking) -> str:
    """Build the full access token URL for the booking."""
    base = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    return f"{base}/bookings/view/{booking.access_token}/"


def _send(subject: str, to_email: str, html_template: str, txt_template: str, context: dict):
    """Low-level send helper — builds multipart email with HTML + text fallback."""
    if not to_email:
        logger.warning('Email skipped — no email address for guest (booking ref %s)', context.get('booking_ref'))
        return

    try:
        text_body = render_to_string(txt_template, context)
        html_body = render_to_string(html_template, context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info('Email "%s" sent to %s', subject, to_email)
    except Exception as exc:
        # Log but never crash the booking flow due to email failure
        logger.exception('Failed to send email "%s" to %s: %s', subject, to_email, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def send_booking_confirmed(booking):
    """
    Send booking confirmation email to guest.
    Triggered: after payment webhook confirms, or after manual booking created.
    """
    ctx = _booking_context(booking)
    ctx['is_manual'] = booking.is_manual

    _send(
        subject=f'Booking Confirmed - {booking.service.name} on {booking.booking_date.strftime("%d %b %Y")}',
        to_email=booking.guest.email,
        html_template='emails/booking_confirmed.html',
        txt_template='emails/booking_confirmed.txt',
        context=ctx,
    )


def send_booking_cancelled(booking, reason: str = ''):
    """
    Send cancellation email to guest.
    Triggered: admin emergency cancel.
    """
    ctx = _booking_context(booking)
    ctx['cancellation_reason'] = reason or 'Unforeseen circumstances'

    _send(
        subject=f'Booking Cancelled — {booking.service.name} on {booking.booking_date.strftime("%d %b %Y")}',
        to_email=booking.guest.email,
        html_template='emails/booking_cancelled.html',
        txt_template='emails/booking_cancelled.txt',
        context=ctx,
    )


def send_booking_reassigned(booking, old_worker_name: str):
    """
    Send therapist update email to guest.
    Triggered: admin worker reassignment.
    """
    ctx = _booking_context(booking)
    ctx['old_worker_name'] = old_worker_name

    _send(
        subject=f'Your Therapist Has Been Updated — {booking.booking_date.strftime("%d %b %Y")}',
        to_email=booking.guest.email,
        html_template='emails/booking_reassigned.html',
        txt_template='emails/booking_reassigned.txt',
        context=ctx,
    )
