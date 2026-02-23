from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-conditions/', views.terms_conditions, name='terms_conditions'),
    path('refund-policy/', views.refund_policy, name='refund_policy'),
    path('team/', views.team, name='team'),
    path('contact/', views.contact, name='contact'),
]
