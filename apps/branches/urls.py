from django.urls import path
from . import views

app_name = 'branches'

urlpatterns = [
    path('', views.branch_list, name='index'),
]
