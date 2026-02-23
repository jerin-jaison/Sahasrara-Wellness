"""Branch CRUD views for the admin dashboard."""
import logging
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.branches.models import Branch
from .decorators import dashboard_admin_required
from .forms import BranchForm

logger = logging.getLogger(__name__)


@dashboard_admin_required
def branch_list(request):
    branches = Branch.objects.all().order_by('name')
    return render(request, 'dashboard/branches/list.html', {
        'branches': branches,
        'page': 'branches',
    })


@dashboard_admin_required
def branch_create(request):
    form = BranchForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        branch = form.save()
        messages.success(request, f'Branch "{branch.name}" created successfully.')
        return redirect('dashboard:branch_list')
    return render(request, 'dashboard/branches/form.html', {
        'form':  form,
        'title': 'Add Branch',
        'page':  'branches',
    })


@dashboard_admin_required
def branch_edit(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    form   = BranchForm(request.POST or None, instance=branch)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Branch "{branch.name}" updated.')
        return redirect('dashboard:branch_list')
    return render(request, 'dashboard/branches/form.html', {
        'form':   form,
        'title':  f'Edit Branch — {branch.name}',
        'branch': branch,
        'page':   'branches',
    })


@require_POST
@dashboard_admin_required
def branch_delete(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    branch.is_active = False
    branch.save(update_fields=['is_active'])
    messages.success(request, f'Branch "{branch.name}" deactivated (soft delete).')
    return redirect('dashboard:branch_list')
