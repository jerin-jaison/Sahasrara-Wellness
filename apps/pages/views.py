from django.shortcuts import render
from apps.branches.models import Branch

def home(request):
    """Landing page with branch finder and about us."""
    branches = Branch.objects.filter(is_active=True)
    return render(request, 'index.html', {'branches': branches})

def about(request):
    """Deep dive into story and philosophy."""
    return render(request, 'about.html')

def privacy_policy(request):
    """Legal privacy policy."""
    return render(request, 'legal/privacy_policy.html')

def terms_conditions(request):
    """Legal terms and conditions."""
    return render(request, 'legal/terms_conditions.html')

def refund_policy(request):
    """Legal refund and cancellation policy."""
    return render(request, 'legal/refund_policy.html')

def team(request):
    """Meet our professional therapists."""
    from apps.workers.models import Worker
    workers = Worker.objects.filter(is_active=True).select_related('branch')
    return render(request, 'team.html', {'workers': workers})

def contact(request):
    """Contact information and branch locations."""
    from apps.branches.models import Branch
    branches = Branch.objects.filter(is_active=True)
    return render(request, 'contact.html', {'branches': branches})
