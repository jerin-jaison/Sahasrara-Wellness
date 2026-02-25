from django.urls import path
from . import views, views_branches, views_services, views_workers, views_reviews

app_name = 'dashboard'

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path('login/',   views.dashboard_login,  name='login'),
    path('logout/',  views.dashboard_logout, name='logout'),

    # ── Core ──────────────────────────────────────────────────────────────
    path('',                                views.overview,         name='overview'),
    path('bookings/',                       views.booking_list,     name='booking_list'),
    path('bookings/<uuid:booking_id>/',     views.booking_detail,   name='booking_detail'),
    path('bookings/<uuid:booking_id>/cancel/',   views.booking_cancel,   name='booking_cancel'),
    path('bookings/<uuid:booking_id>/complete/', views.booking_complete, name='booking_complete'),
    path('bookings/<uuid:booking_id>/reassign/', views.booking_reassign, name='booking_reassign'),
    path('manual/',                         views.manual_booking,   name='manual_booking'),
    path('revenue-data/',                   views.revenue_data,     name='revenue_data'),

    # ── Branch CRUD ────────────────────────────────────────────────────────
    path('branches/',                      views_branches.branch_list,   name='branch_list'),
    path('branches/new/',                  views_branches.branch_create, name='branch_create'),
    path('branches/<uuid:pk>/edit/',       views_branches.branch_edit,   name='branch_edit'),
    path('branches/<uuid:pk>/delete/',     views_branches.branch_delete, name='branch_delete'),

    # ── Service CRUD ──────────────────────────────────────────────────────
    path('services/',                      views_services.service_list,   name='service_list'),
    path('services/new/',                  views_services.service_create, name='service_create'),
    path('services/<uuid:pk>/edit/',       views_services.service_edit,   name='service_edit'),
    path('services/<uuid:pk>/delete/',     views_services.service_delete, name='service_delete'),

    # ── Worker CRUD ───────────────────────────────────────────────────────
    path('workers/',                       views_workers.worker_list,   name='worker_list'),
    path('workers/new/',                   views_workers.worker_create, name='worker_create'),
    path('workers/<uuid:pk>/edit/',        views_workers.worker_edit,   name='worker_edit'),
    path('workers/<uuid:pk>/delete/',      views_workers.worker_delete, name='worker_delete'),

    # ── Review CRUD ───────────────────────────────────────────────────────
    path('reviews/',                       views_reviews.review_list,   name='review_list'),
    path('reviews/new/',                   views_reviews.review_create, name='review_create'),
    path('reviews/<uuid:pk>/edit/',        views_reviews.review_edit,   name='review_edit'),
    path('reviews/<uuid:pk>/delete/',      views_reviews.review_delete, name='review_delete'),
]
