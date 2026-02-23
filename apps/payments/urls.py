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

    # Slot/booking expired — lock TTL elapsed
    path('expired/<uuid:booking_id>/', views.payment_expired, name='expired'),
]
