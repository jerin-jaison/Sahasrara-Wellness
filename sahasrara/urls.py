"""
URL configuration for Sahasrara Wellness Booking System.
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('', include('apps.pages.urls', namespace='pages')),
    path('branches/', include('apps.branches.urls', namespace='branches')),
    path('services/', include('apps.services.urls', namespace='services')),
    path('workers/', include('apps.workers.urls', namespace='workers')),
    path('bookings/', include('apps.bookings.urls', namespace='bookings')),
    path('payments/', include('apps.payments.urls', namespace='payments')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
]

# Custom Error Handlers
handler404 = 'apps.pages.views.error_404'
handler500 = 'apps.pages.views.error_500'
handler403 = 'apps.pages.views.error_403'

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
