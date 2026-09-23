from django.shortcuts import render
from .models import Worker

def worker_list(request):
    """Public list of active team members/therapists."""
    workers = Worker.objects.filter(is_active=True).select_related('branch')
    return render(request, 'team.html', {'workers': workers})
