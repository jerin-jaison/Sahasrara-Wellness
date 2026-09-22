from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Initiate payment — called after booking lock is acquired
    path('initiate/<uuid:booking_id>/', views.initiate_payment, name='initiate'),

    # Razorpay redirects here after modal completes (success or dismiss)
    path('callback/', views.payment_callback, name='callback'),

    # Razorpay server-side webhook (CSRF-exempt)
    path('webhook/', views.razorpay_webhook, name='webhook'),

    # Retry payment (still within lock TTL)
    path('retry/<uuid:booking_id>/', views.payment_retry, name='retry'),


    # Payment Receipt
    path('receipt/<uuid:booking_id>/', views.view_receipt, name='receipt'),
    path('receipt/download/<uuid:booking_id>/', views.download_receipt_pdf, name='receipt_pdf'),
]
