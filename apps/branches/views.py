from django.shortcuts import render
from .models import Branch

def branch_list(request):
    """Public list of active branches."""
    branches = Branch.objects.filter(is_active=True)
    return render(request, 'contact.html', {'branches': branches})
