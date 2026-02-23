"""Worker CRUD views for the admin dashboard."""
import logging
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.workers.models import Worker
from .decorators import dashboard_admin_required
from .forms import WorkerForm

logger = logging.getLogger(__name__)


@dashboard_admin_required
def worker_list(request):
    workers = Worker.objects.select_related('branch').order_by('branch__name', 'name')
    return render(request, 'dashboard/workers/list.html', {
        'workers': workers,
        'page': 'workers',
    })


@dashboard_admin_required
def worker_create(request):
    form = WorkerForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        worker = form.save()
        messages.success(
            request,
            f'Therapist "{worker.name}" created. '
            'Remember to configure their working schedule in Django Admin → Worker Schedules.'
        )
        return redirect('dashboard:worker_list')
    return render(request, 'dashboard/workers/form.html', {
        'form':  form,
        'title': 'Add Therapist',
        'page':  'workers',
    })


@dashboard_admin_required
def worker_edit(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    form   = WorkerForm(request.POST or None, request.FILES or None, instance=worker)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Therapist "{worker.name}" updated.')
        return redirect('dashboard:worker_list')
    return render(request, 'dashboard/workers/form.html', {
        'form':   form,
        'title':  f'Edit Therapist — {worker.name}',
        'worker': worker,
        'page':   'workers',
    })


@require_POST
@dashboard_admin_required
def worker_delete(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    worker.is_active = False
    worker.save(update_fields=['is_active'])
    messages.success(request, f'Therapist "{worker.name}" deactivated.')
    return redirect('dashboard:worker_list')
