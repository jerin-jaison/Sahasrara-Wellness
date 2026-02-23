"""
Booking flow URLs.

Flow:
  /book/                           Step 1: Branch selection
  /book/services/                  Step 2: Service selection
  /book/workers/                   Step 3: Worker selection  
  /book/date/                      Step 4: Date selection
  /book/slots/                     Step 5: Slot selection
  /book/info/                      Step 6: Guest info
  /book/review/                    Step 7: Review & lock
  /book/confirmation/<uuid>/       Step 8: Booking confirmed page
  /book/api/slots/                 AJAX: slot grid for a worker+service+date
  /book/api/workers/               AJAX: workers available for any-worker mode
  /book/my/                        Guest inbox (session OR phone lookup)
  /book/view/<access_token>/       Token-based booking view (from email link)
  /book/cancel-lock/               Release current slot lock (go back)
"""
from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # ── Multi-step booking flow ────────────────────────────────────────────────
    path('',                        views.step1_branch,       name='step1_branch'),
    path('services/',               views.step2_services,     name='step2_services'),
    path('workers/',                views.step3_workers,      name='step3_workers'),
    path('date/',                   views.step4_date,         name='step4_date'),
    path('slots/',                  views.step5_slots,        name='step5_slots'),
    path('info/',                   views.step6_info,         name='step6_info'),
    path('review/',                 views.step7_review,       name='step7_review'),
    path('confirmation/<uuid:booking_id>/', views.booking_confirmation, name='confirmation'),

    # ── AJAX endpoints ─────────────────────────────────────────────────────────
    path('api/slots/',              views.api_slots,          name='api_slots'),
    path('api/workers/',            views.api_available_workers, name='api_workers'),

    # ── Guest inbox & token access ─────────────────────────────────────────────
    path('my/',                     views.guest_inbox,        name='inbox'),
    path('view/<uuid:access_token>/', views.booking_detail_token, name='detail_token'),

    # ── Lock management ────────────────────────────────────────────────────────
    path('cancel-lock/',            views.cancel_lock,        name='cancel_lock'),
]
