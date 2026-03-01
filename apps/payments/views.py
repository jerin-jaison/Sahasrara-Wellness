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
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from xhtml2pdf import pisa
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.bookings.models import Booking, BookingStatus, BookingStatusLog
from apps.bookings.session import get_booking_session

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




# ─────────────────────────────────────────────────────────────────────────────
# Step: Initiate Payment → create Razorpay order, render modal
# ─────────────────────────────────────────────────────────────────────────────

def initiate_payment(request, booking_id):
    """
    Called right after step7_review creates a PENDING_PAYMENT booking.
    Creates a Razorpay order and renders the payment page with the JS modal.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('service', 'worker', 'branch', 'guest', 'payment'),
        id=booking_id,
    )

    # 1. If already confirmed, skip to success
    if booking.status == BookingStatus.CONFIRMED:
        return redirect('bookings:confirmation', booking_id=booking.id)

    # 2. Check if a Payment record already exists
    payment = getattr(booking, 'payment', None)

    if payment is None:
        # Determine charge amount (deposit vs full) - fallback to deposit if session lost
        s = get_booking_session(request)
        payment_type = s.get('payment_type', 'deposit') if s else 'deposit'
        
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
        
        # NEW: Store order_id on booking for session-independent lookup (Requirement 1)
        booking.razorpay_order_id = order_data['id']
        booking.save(update_fields=['razorpay_order_id'])

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

        # 1. DB Lookup via Razorpay Order ID on Booking (Requirement 1)
        logger.info("Callback: Booking lookup via order_id %s", razorpay_order_id)
        booking = Booking.objects.filter(razorpay_order_id=razorpay_order_id).first()
        
        if not booking:
            logger.warning('Callback ERROR: booking not found for order %s', razorpay_order_id)
            return redirect('payments:error')

        # 2. Verify Razorpay signature securely
        if not _verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            logger.warning('Callback ERROR: Invalid signature for booking %s', booking.id)
            # If signature fails, log it and redirect to retry/failed page
            return redirect('payments:retry', booking_id=booking.id)

        # 3. Confirm booking here so UI updates immediately (webhook will idempotent skip if this wins)
        logger.info("Callback: Signature verified for booking %s. Confirming immediately.", booking.id)

        payment = getattr(booking, 'payment', None)
        amount_paid = payment.amount if payment else booking.service.price

        Booking.confirm_payment(
            booking_id=booking.id,
            razorpay_payment_id=razorpay_payment_id,
            amount_paid=amount_paid,
            razorpay_signature=razorpay_signature,
            source='callback',
        )

        # Update session inbox if session exists (optional convenience)
        if request.session:
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

    # 5. Success redirect using token (Session Independent)
    return redirect(f"/bookings/confirmation/{booking.id}/?token={booking.access_token}")


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
        logger.warning('Webhook: Received non-POST request.')
        return HttpResponse(status=405)

    raw_body = request.body
    signature = request.headers.get('X-Razorpay-Signature', '')
    logger.info('Webhook: Received event. Signature length: %d', len(signature))

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

            # Lookup Booking via razorpay_order_id directly (Requirement 1 & 10)
            booking = Booking.objects.select_related('service', 'guest').filter(razorpay_order_id=razorpay_order_id).first()
            if not booking:
                logger.warning('Webhook ERROR: Booking not found for order %s', razorpay_order_id)
                return HttpResponse(status=200)

            # Ensure Payment record exists (fetch or create if missing/delayed)
            payment, created = Payment.objects.get_or_create(
                booking=booking,
                defaults={
                    'razorpay_order_id': razorpay_order_id,
                    'amount': booking.amount_paid or booking.service.price,
                    'currency': 'INR',
                    'status': PaymentStatus.CREATED,
                }
            )

            # Record event ID for idempotency before confirming
            payment.webhook_event_id = event_id or None
            payment.webhook_payload  = payload
            payment.save(update_fields=['webhook_event_id', 'webhook_payload'])

            # Authoritative confirmation (Requirement 3)
            logger.info("Authoritative confirmation via webhook: event=%s, payment=%s, booking=%s", 
                        event_id, razorpay_payment_id, booking.id)
            
            Booking.confirm_payment(
                booking_id=booking.id,
                razorpay_payment_id=razorpay_payment_id,
                amount_paid=payment.amount,
                source='webhook',
            )
            logger.info("Booking %s confirmed successfully via webhook event %s", booking.id, event_id)
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
    try:
        booking = Booking.objects.select_related('service', 'worker', 'branch', 'guest').get(id=booking_id)
    except Booking.DoesNotExist:
        return redirect('payments:expired', booking_id=booking_id)

    if booking.status == BookingStatus.CONFIRMED:
        return redirect('bookings:confirmation', booking_id=booking.id)

    # Prevent retry if payment was already captured (webhook might be a few seconds late)
    payment = getattr(booking, 'payment', None)
    if payment and payment.status == PaymentStatus.CAPTURED:
        logger.info('Retry prevented: Payment for %s is already CAPTURED.', booking.id)
        return redirect(f"/payments/success-pending/{booking.id}/?token={booking.access_token}")

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


