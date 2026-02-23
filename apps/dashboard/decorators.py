"""
Dashboard authentication decorator.

Replaces the @login_required + @staff_member_required stack.
Redirects all unauthenticated / non-staff requests to the dashboard
login page at /dashboard/login/, preserving the ?next= URL for
post-login redirect.
"""
from functools import wraps
from django.shortcuts import redirect

DASHBOARD_LOGIN = '/dashboard/login/'


def dashboard_admin_required(view_func):
    """Require is_authenticated + is_staff. Redirect to dashboard login otherwise."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect(f'{DASHBOARD_LOGIN}?next={request.path}')
        return view_func(request, *args, **kwargs)
    return wrapper
