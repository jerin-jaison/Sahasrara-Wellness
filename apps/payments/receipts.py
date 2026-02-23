"""
Receipt data logic for Sahasrara Wellness.
Prepares context for receipt.html.
"""
from django.conf import settings
from django.utils import timezone

def get_receipt_context(booking):
    """
    Gathers all necessary information for the payment receipt.
    Works for both full and partial (deposit) payments.
    """
    payment = getattr(booking, 'payment', None)
    
    # Financials
    total_amount = booking.service.price
    amount_paid = booking.amount_paid
    balance_due = total_amount - amount_paid
    
    # Labels
    payment_type_label = "Full Payment"
    if amount_paid < total_amount:
        # Check if it was explicitly a deposit (usually 10% or similar)
        payment_type_label = "Advance Deposit (10%)"

    return {
        'booking': booking,
        'payment': payment,
        'business': {
            'name': 'Sahasrara Wellness',
            'phone': '+91 97470 00210',
            'email': 'bookings@sahasrarawellness.com',
            'gstin_placeholder': 'GSTIN: [To be updated]',
        },
        'guest': {
            'name': booking.guest.name,
            'phone': booking.guest.phone,
            'email': booking.guest.email,
        },
        'transaction': {
            'reference_id': booking.id_short,
            'razorpay_payment_id': payment.razorpay_payment_id if payment else 'N/A',
            'razorpay_order_id': payment.razorpay_order_id if payment else 'N/A',
            'date': payment.paid_at if (payment and payment.paid_at) else timezone.now(),
            'status': booking.payment_status,
            'payment_type': payment_type_label,
        },
        'financials': {
            'total': total_amount,
            'paid': amount_paid,
            'balance': max(0, balance_due),
            'currency': 'INR',
        },
        'appointment': {
            'service': booking.service.name,
            'therapist': booking.worker.name,
            'branch': booking.branch.name,
            'date': booking.booking_date,
            'time': booking.start_time,
        }
    }
