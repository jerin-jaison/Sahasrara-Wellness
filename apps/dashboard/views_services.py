"""Service CRUD views for the admin dashboard."""
import logging
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.services.models import Service
from .decorators import dashboard_admin_required
from .forms import ServiceForm

logger = logging.getLogger(__name__)


@dashboard_admin_required
def service_list(request):
    services = Service.objects.prefetch_related('branches').order_by('name')
    return render(request, 'dashboard/services/list.html', {
        'services': services,
        'page': 'services',
    })


@dashboard_admin_required
def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        durations = form.cleaned_data.get('durations', [])
        branches = form.cleaned_data.get('branches', [])
        
        # Create a new Service row for each duration selected
        created_count = 0
        for d_min in durations:
            d_int = int(d_min)
            # Pick the correct price for this duration
            price = form.cleaned_data.get(f'price_{d_int}')
            
            svc = Service(
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description'],
                duration_minutes=d_int,
                buffer_minutes=form.cleaned_data['buffer_minutes'],
                price=price,
                is_active=form.cleaned_data['is_active'],
            )
            svc.save()
            svc.branches.set(branches)
            created_count += 1
            
        messages.success(request, f'Successfully created {created_count} service variants.')
        return redirect('dashboard:service_list')
        
    return render(request, 'dashboard/services/form.html', {
        'form':  form,
        'title': 'Add Service',
        'page':  'services',
    })


@dashboard_admin_required
def service_edit(request, pk):
    svc = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, instance=svc)
    
    if request.method == 'POST' and form.is_valid():
        durations = form.cleaned_data.get('durations', [])
        branches = form.cleaned_data.get('branches', [])
        
        # Save the primary instance (this updates the one we're currently editing)
        # Note: We must set its duration based on what's available
        # If the current duration is still in the checked list, keep it.
        # Otherwise, pick the first one checked.
        old_duration = svc.duration_minutes
        if str(old_duration) in durations:
            svc.duration_minutes = old_duration
        else:
            svc.duration_minutes = int(durations[0])
            
        svc.name = form.cleaned_data['name']
        svc.description = form.cleaned_data['description']
        svc.buffer_minutes = form.cleaned_data['buffer_minutes']
        svc.price = form.cleaned_data.get(f'price_{svc.duration_minutes}')
        svc.is_active = form.cleaned_data['is_active']
        svc.save()
        svc.branches.set(branches)
        
        # Now handle sync: for other selected durations, update or create.
        for d_min in durations:
            d_int = int(d_min)
            if d_int == svc.duration_minutes:
                continue
            
            price = form.cleaned_data.get(f'price_{d_int}')
                
            # Check if another variant with SAME NAME already exists for this duration
            other_svc = Service.objects.filter(name=svc.name, duration_minutes=d_int).exclude(pk=svc.pk).first()
            if other_svc:
                other_svc.description = svc.description
                other_svc.buffer_minutes = svc.buffer_minutes
                other_svc.price = price
                other_svc.is_active = svc.is_active
                other_svc.save()
                other_svc.branches.set(branches)
            else:
                # Create a NEW variant
                new_v = Service(
                    name=svc.name,
                    description=svc.description,
                    duration_minutes=d_int,
                    buffer_minutes=svc.buffer_minutes,
                    price=price,
                    is_active=svc.is_active,
                )
                new_v.save()
                new_v.branches.set(branches)
                
        messages.success(request, f'Service "{svc.name}" and its variants updated.')
        return redirect('dashboard:service_list')
        
    return render(request, 'dashboard/services/form.html', {
        'form':    form,
        'title':   f'Edit Service — {svc.name}',
        'service': svc,
        'page':    'services',
    })


@require_POST
@dashboard_admin_required
def service_delete(request, pk):
    svc = get_object_or_404(Service, pk=pk)
    svc.is_active = False
    svc.save(update_fields=['is_active'])
    messages.success(request, f'Service "{svc.name}" deactivated.')
    return redirect('dashboard:service_list')
