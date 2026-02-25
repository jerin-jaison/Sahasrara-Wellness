"""
Payment views for Sahasrara Wellness.

Flow:
  1. step7_review POST → acquire lock → create PENDING_PAYMENT booking
                       → redirect to initiate_payment
  2. initiate_payment  → create Razorpay order → render payment.html (JS modal)
  3. payment_callback  → Razorpay redirects here after modal closes (success OR fail)
                       → verify signature → CONFIRMED → send email → confirmation
  4. razorpay_webhook  → Razorpay server-side event → authoritative confirmation
  5. payment_retry     → user can retry payment within lock TTL
  6. payment_expired   → booking expired; guide user to rebook
"""
import hashlib
import hmac
import json
import logging

import razorpay
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from xhtml2pdf import pisa
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.bookings.models import Booking, BookingStatus, BookingStatusLog
from apps.bookings.session import get_booking_session
from apps.notifications.emails import send_booking_confirmed
from .models import Payment, PaymentStatus
from .receipts import get_receipt_context

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Payment Receipt
# ─────────────────────────────────────────────────────────────────────────────

def view_receipt(request, booking_id):
    """
    Securely view a payment receipt for a confirmed booking.
    Guests can access via access_token OR active session.
    """
    token = request.GET.get('token')
    
    # Try fetching via access_token first (more secure for email links)
    if token:
        booking = get_object_or_404(
            Booking.objects.select_related('service', 'worker', 'branch', 'guest', 'payment'),
            id=booking_id,
            access_token=token
        )
    else:
        # Fallback to inbox session check
        inbox = request.session.get('booking_inbox', [])
        if str(booking_id) not in inbox:
            # If not in session, they must provide the token
            return render(request, 'payments/error.html', {
                'message': 'Access denied. Please use the link sent to your email or mobile.',
                'title': 'Restricted Access'
            })
            
        booking = get_object_or_404(
            Booking.objects.select_related('service', 'worker', 'branch', 'guest', 'payment'),
            id=booking_id
        )

    # Business rule: only show receipts for confirmed/paid bookings
    if booking.status not in [BookingStatus.CONFIRMED, BookingStatus.COMPLETED]:
         return render(request, 'payments/error.html', {
                'message': 'Receipt is only available for confirmed or completed bookings.',
            })

    context = get_receipt_context(booking)
    return render(request, 'payments/receipt.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Download PDF Receipt
# ─────────────────────────────────────────────────────────────────────────────

def download_receipt_pdf(request, booking_id):
    """
    Generates and downloads a PDF version of the payment receipt.
    """
    token = request.GET.get('token')
    
    if token:
        booking = get_object_or_404(
            Booking.objects.select_related('service', 'worker', 'branch', 'guest', 'payment'),
            id=booking_id,
            access_token=token
        )
    else:
        inbox = request.session.get('booking_inbox', [])
        if str(booking_id) not in inbox:
            return HttpResponse("Access Denied", status=403)
            
        booking = get_object_or_404(
            Booking.objects.select_related('service', 'worker', 'branch', 'guest', 'payment'),
            id=booking_id
        )

    if booking.status not in [BookingStatus.CONFIRMED, BookingStatus.COMPLETED]:
         return HttpResponse("Receipt not available", status=400)

    context = get_receipt_context(booking)
    
    # Render PDF
    template = get_template('payments/receipt_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{booking.id_short}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Razorpay client (lazy singleton)
# ─────────────────────────────────────────────────────────────────────────────

def _razorpay_client():
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature (HMAC-SHA256)."""
    secret = settings.RAZORPAY_KEY_SECRET.encode()
    message = f"{order_id}|{payment_id}".encode()
    computed = hmac.new(key=secret, msg=message, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def _verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET.encode()
    computed = hmac.new(key=secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


@transaction.atomic
def _confirm_booking(booking: Booking, payment: Payment, razorpay_payment_id: str,
                     razorpay_signature: str = '', source: str = 'webhook') -> None:
    """
    Transition booking to CONFIRMED and update payment record.
    Thread-safe & Idempotent implementation with select_for_update to avoid race conditions.
    """
    logger.info('Confirmation attempt for booking %s via %s [payment_id: %s]', 
                booking.id, source, razorpay_payment_id)

    # 1. Idempotent Payment Guard: Has this payment ID already been used to confirm something?
    if Payment.objects.filter(razorpay_payment_id=razorpay_payment_id, status=PaymentStatus.CAPTURED).exists():
        logger.info('Payment %s already processed/captured — skipping.', razorpay_payment_id)
        return

    # 2. Row lock via select_for_update within atomic transaction
    booking = Booking.objects.select_for_update().get(id=booking.id)

    # 3. Booking State Guard: Is it already confirmed?
    if booking.status == BookingStatus.CONFIRMED:
        logger.info('Booking %s already CONFIRMED — skipping.', booking.id)
        return

    old_status = booking.status
    booking.status = BookingStatus.CONFIRMED
    booking.payment_status = 'PAID'
    booking.amount_paid = payment.amount
    booking.save(update_fields=['status', 'payment_status', 'amount_paid', 'updated_at'])

    payment.status = PaymentStatus.CAPTURED
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.paid_at = timezone.now()
    payment.save(update_fields=[
        'status', 'razorpay_payment_id', 'razorpay_signature', 'paid_at',
    ])

    BookingStatusLog.objects.create(
        booking=booking,
        from_status=old_status,
        to_status=BookingStatus.CONFIRMED,
        changed_by=source,
        reason=f'Payment captured via {source}',
    )

    try:
        send_booking_confirmed(booking)
    except Exception as e:
        logger.exception("Email notification failed after confirmation: %s", e)

    logger.info('Booking %s successfully CONFIRMED via %s.', booking.id, source)


# ─────────────────────────────────────────────────────────────────────────────
# Step: Initiate Payment → create Razorpay order, render modal
# ─────────────────────────────────────────────────────────────────────────────

def initiate_payment(request, booking_id):
    """
    Called right after step7_review creates a PENDING_PAYMENT booking.
    Creates a Razorpay order and renders the payment page with the JS modal.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('service', 'worker', 'branch', 'guest'),
        id=booking_id,
        status=BookingStatus.PENDING_PAYMENT,
    )

    # Check if a Payment record already exists (e.g. back-button hit)
    payment = getattr(booking, 'payment', None)

    if payment is None:
        # Determine charge amount (deposit vs full)
        s = get_booking_session(request)
        payment_type = s.get('payment_type', 'deposit')
        
        charge_amount = booking.service.price
        if payment_type == 'deposit':
            charge_amount = booking.service.deposit_price

        # Create a fresh Razorpay order
        client = _razorpay_client()
        amount_paise = int(charge_amount * 100)  # Razorpay uses smallest unit
        try:
            order_data = client.order.create({
                'amount': amount_paise,
                'currency': 'INR',
                'receipt': str(booking.id)[:40],
                'notes': {
                    'booking_id': str(booking.id),
                    'payment_type': payment_type,
                    'guest_name': booking.guest.name,
                    'service': booking.service.name,
                },
            })
        except Exception as exc:
            logger.exception('Razorpay order creation failed for booking %s: %s', booking.id, exc)
            return render(request, 'payments/error.html', {
                'message': 'Could not connect to the payment gateway. Please try again.',
                'booking': booking,
            })

        payment = Payment.objects.create(
            booking=booking,
            razorpay_order_id=order_data['id'],
            amount=charge_amount,
            currency='INR',
            status=PaymentStatus.CREATED,
        )

    # Build callback URL
    callback_url = request.build_absolute_uri(
        f'/payments/callback/'
    )

    return render(request, 'payments/payment.html', {
        'booking':          booking,
        'payment':          payment,
        'razorpay_key_id':  settings.RAZORPAY_KEY_ID,
        'amount_paise':     int(payment.amount * 100),
        'callback_url':     callback_url,
        'guest_name':       booking.guest.name,
        'guest_email':      booking.guest.email or '',
        'guest_phone':      booking.guest.phone or '',
        'expired_url':      request.build_absolute_uri(f'/payments/expired/{booking.id}/'),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Payment Callback (Razorpay redirects here after modal)
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def payment_callback(request):
    """
    Razorpay posts payment result to this URL after the JS modal completes.
    Verifies signature and transitions booking to CONFIRMED on success.
    On failure: redirect to retry page.
    """
    try:
        razorpay_order_id  = request.POST.get('razorpay_order_id', '')
        razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_signature = request.POST.get('razorpay_signature', '')

        try:
            payment = Payment.objects.select_related('booking').get(razorpay_order_id=razorpay_order_id)
        except Payment.DoesNotExist:
            logger.warning('Callback: order not found %s', razorpay_order_id)
            return redirect('bookings:step1_branch')

        booking = payment.booking

        # 1. Verify signature
        if not _verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            logger.warning('Signature verification FAILED for order %s', razorpay_order_id)
            return redirect('payments:retry', booking_id=booking.id)

        # 2. UI ONLY: Do NOT update booking status here.
        # Confirmation is handled strictly by the webhook.
        logger.info('Callback (UI-only) verified signature for booking %s. Redirecting to success_pending.', booking.id)

        # Update session inbox (so they can see the booking in their list)
        inbox = request.session.get('booking_inbox', [])
        bid = str(booking.id)
        if bid not in inbox:
            inbox.append(bid)
        request.session['booking_inbox'] = inbox
        request.session.modified = True

    except Exception as exc:
        logger.exception('Fatal error in payment_callback: %s', exc)
        return render(request, 'payments/error.html', {
            'message': 'An unexpected error occurred. Our team will verify your payment shortly.',
            'title': 'Confirmation Processing'
        })

    return redirect('payments:success_pending', booking_id=booking.id)


# ─────────────────────────────────────────────────────────────────────────────
# Razorpay Webhook (server-to-server — authoritative)
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
def razorpay_webhook(request):
    """
    Razorpay fires this endpoint for every payment event.
    Must be CSRF-exempt; security comes from HMAC-SHA256 signature check.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    raw_body = request.body
    signature = request.headers.get('X-Razorpay-Signature', '')

    # Skip signature check if webhook secret not configured (dev convenience)
    if settings.RAZORPAY_WEBHOOK_SECRET and settings.RAZORPAY_WEBHOOK_SECRET != 'your-webhook-secret':
        if not _verify_webhook_signature(raw_body, signature):
            logger.warning('Webhook signature verification failed.')
            return HttpResponse(status=400)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event = payload.get('event', '')
    event_id = payload.get('id', '')

    # Idempotency: skip if already processed
    if event_id and Payment.objects.filter(webhook_event_id=event_id).exists():
        logger.info('Webhook event %s already processed — skipping.', event_id)
        return HttpResponse(status=200)

    if event == 'payment.captured':
        try:
            item = payload['payload']['payment']['entity']
            razorpay_order_id  = item['order_id']
            razorpay_payment_id = item['id']

            payment = Payment.objects.select_related(
                'booking__service', 'booking__worker',
                'booking__branch', 'booking__guest',
            ).get(razorpay_order_id=razorpay_order_id)

            # Record event ID for idempotency before confirming
            payment.webhook_event_id = event_id or None
            payment.webhook_payload  = payload
            payment.save(update_fields=['webhook_event_id', 'webhook_payload'])

            # Webhook is the source of truth for confirmation
            _confirm_booking(
                booking=payment.booking,
                payment=payment,
                razorpay_payment_id=razorpay_payment_id,
                source='webhook',
            )
        except Payment.DoesNotExist:
            logger.warning('Webhook: Payment not found for order %s', razorpay_order_id)
        except Exception as exc:
            # Webhook must never crash or return 500
            logger.exception('Webhook processing error: %s', exc)
            return HttpResponse(status=200)

    return HttpResponse(status=200)


# ─────────────────────────────────────────────────────────────────────────────
# Retry Payment
# ─────────────────────────────────────────────────────────────────────────────

def payment_retry(request, booking_id):
    """
    Show retry page. If slot lock is still active, let user try again.
    If lock expired, redirect to expired page.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('service', 'worker', 'branch', 'guest'),
        id=booking_id,
    )

    if booking.status == BookingStatus.CONFIRMED:
        return redirect('bookings:confirmation', booking_id=booking.id)

    # Check if lock is still valid
    lock = booking.slot_lock if hasattr(booking, 'slot_lock') else None
    lock_expired = True
    if lock and not lock.released and lock.expires_at > timezone.now():
        lock_expired = False

    if lock_expired or booking.status == BookingStatus.EXPIRED:
        return redirect('payments:expired', booking_id=booking.id)

    return render(request, 'payments/retry.html', {'booking': booking})


# ─────────────────────────────────────────────────────────────────────────────
# Payment Expired
# ─────────────────────────────────────────────────────────────────────────────

def payment_expired(request, booking_id):
    """Booking/lock expired — slot released. Guide user to rebook."""
    booking = get_object_or_404(
        Booking.objects.select_related('service', 'branch'),
        id=booking_id,
    )
    return render(request, 'payments/expired.html', {'booking': booking})


# ─────────────────────────────────────────────────────────────────────────────
# Success Pending (Intermediate state for UI-only callback)
# ─────────────────────────────────────────────────────────────────────────────

def success_pending(request, booking_id):
    """
    Intermediate page shown while we wait for webhook confirmation.
    Automatically redirects to confirmation page once booking status is CONFIRMED.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('service', 'branch'),
        id=booking_id
    )

    if booking.status == BookingStatus.CONFIRMED:
        return redirect('bookings:confirmation', booking_id=booking.id)

    return render(request, 'payments/success_pending.html', {
        'booking': booking,
    })
