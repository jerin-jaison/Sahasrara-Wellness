from django.shortcuts import render
from collections import defaultdict
from .models import Service

def services_index(request):
    """Catalog of available treatments."""
    # Get all active services
    all_services = Service.objects.filter(is_active=True).prefetch_related('branches')
    
    # Group by name
    grouped = defaultdict(list)
    for s in all_services:
        grouped[s.name].append(s)
    
    # Sort variants by duration
    for name in grouped:
        grouped[name].sort(key=lambda x: x.duration_minutes)
        
    context = {
        'grouped_services': dict(grouped),
    }
    return render(request, 'services.html', context)
