"""
Admin Dashboard views — updated with custom dashboard_admin_required decorator
and dashboard login/logout views.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST, require_GET

from apps.bookings.models import Booking, BookingStatus, BookingStatusLog, PaymentStatus
from apps.branches.models import Branch
from apps.guests.models import Guest
from apps.services.models import Service
from apps.workers.models import Worker
from apps.notifications.emails import send_booking_cancelled, send_booking_reassigned

from .decorators import dashboard_admin_required

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Auth views
# ─────────────────────────────────────────────────────────────────────────────

def dashboard_login(request):
    """Custom dashboard login page. Redirects staff users to ?next or overview."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(request.GET.get('next', 'dashboard:overview'))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            next_url = request.POST.get('next', '') or request.GET.get('next', '')
            return redirect(next_url or 'dashboard:overview')
        elif user is not None and not user.is_staff:
            messages.error(request, 'Your account does not have admin access.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'dashboard/login.html', {
        'next': request.GET.get('next', ''),
    })


def dashboard_logout(request):
    logout(request)
    return redirect('dashboard:login')


# ─────────────────────────────────────────────────────────────────────────────
# Overview / KPI dashboard
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_admin_required
def overview(request):
    today = date.today()

    qs = Booking.objects.all()
    kpis = {
        'today_confirmed':  qs.filter(booking_date=today, status=BookingStatus.CONFIRMED).count(),
        'today_total':      qs.filter(booking_date=today).exclude(status=BookingStatus.EXPIRED).count(),
        'pending_payment':  qs.filter(status=BookingStatus.PENDING_PAYMENT).count(),
        'month_confirmed':  qs.filter(
            booking_date__year=today.year,
            booking_date__month=today.month,
            status=BookingStatus.CONFIRMED,
        ).count(),
        'month_revenue': qs.filter(
            booking_date__year=today.year,
            booking_date__month=today.month,
            status=BookingStatus.CONFIRMED,
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0'),
        'total_revenue': qs.filter(status=BookingStatus.CONFIRMED).aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0'),
    }

    todays_bookings = (
        Booking.objects
        .filter(booking_date=today)
        .exclude(status__in=[BookingStatus.EXPIRED, BookingStatus.CANCELLED])
        .select_related('guest', 'service', 'worker', 'branch')
        .order_by('start_time')
    )

    week_end = today + timedelta(days=7)
    upcoming = Booking.objects.filter(
        booking_date__gt=today,
        booking_date__lte=week_end,
        status=BookingStatus.CONFIRMED,
    ).count()

    recent_bookings = (
        Booking.objects
        .select_related('guest', 'service', 'worker', 'branch')
        .exclude(status=BookingStatus.EXPIRED)
        .order_by('-created_at')[:5]
    )

    return render(request, 'dashboard/overview.html', {
        'kpis':            kpis,
        'todays_bookings': todays_bookings,
        'upcoming':        upcoming,
        'recent_bookings': recent_bookings,
        'today':           today,
        'page': 'overview',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Booking List
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_admin_required
def booking_list(request):
    qs = (
        Booking.objects
        .select_related('guest', 'service', 'worker', 'branch')
        .order_by('-booking_date', '-start_time')
    )

    status_filter = request.GET.get('status', '')
    branch_filter = request.GET.get('branch', '')
    search        = request.GET.get('q', '').strip()
    date_from     = request.GET.get('date_from', '')
    date_to       = request.GET.get('date_to', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if branch_filter:
        qs = qs.filter(branch_id=branch_filter)
    if search:
        qs = qs.filter(
            Q(guest__name__icontains=search) |
            Q(guest__phone__icontains=search) |
            Q(service__name__icontains=search) |
            Q(worker__name__icontains=search)
        )
    if date_from:
        d_from = parse_date(date_from)
        if d_from:
            qs = qs.filter(booking_date__gte=d_from)
    if date_to:
        d_to = parse_date(date_to)
        if d_to:
            qs = qs.filter(booking_date__lte=d_to)

    branches = Branch.objects.filter(is_active=True)

    return render(request, 'dashboard/booking_list.html', {
        'bookings':       qs,
        'branches':       branches,
        'status_choices': BookingStatus.choices,
        'page': 'bookings',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Booking Detail
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_admin_required
def booking_detail(request, booking_id):
    pk = booking_id
    booking = get_object_or_404(
        Booking.objects.select_related('guest', 'service', 'worker', 'branch', 'payment'),
        id=pk
    )
    status_logs = booking.status_logs.all().order_by('changed_at')
    branch_workers = Worker.objects.filter(branch=booking.branch, is_active=True).exclude(id=booking.worker_id)

    return render(request, 'dashboard/booking_detail.html', {
        'booking':        booking,
        'status_logs':    status_logs,
        'branch_workers': branch_workers,
        'page': 'bookings',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Actions
# ─────────────────────────────────────────────────────────────────────────────

@require_POST
@dashboard_admin_required
def booking_cancel(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    reason  = request.POST.get('reason', '').strip() or 'Cancelled by admin'

    if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.PENDING_PAYMENT):
        messages.error(request, 'Cannot cancel booking in its current state.')
        return redirect('dashboard:booking_detail', booking_id=booking_id)

    booking.cancel(changed_by=request.user.username, reason=reason)
    try:
        send_booking_cancelled(booking, reason=reason)
    except Exception:
        logger.exception('Cancellation email failed for booking %s', booking_id)

    messages.success(request, f'Booking #{str(booking_id)[:8].upper()} cancelled.')
    return redirect('dashboard:booking_detail', booking_id=booking_id)


@require_POST
@dashboard_admin_required
def booking_complete(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if booking.status != BookingStatus.CONFIRMED:
        messages.error(request, 'Only confirmed bookings can be completed.')
        return redirect('dashboard:booking_detail', booking_id=booking_id)

    booking.complete(changed_by=request.user.username)
    messages.success(request, f'Booking #{str(booking_id)[:8].upper()} marked as completed.')
    return redirect('dashboard:booking_detail', booking_id=booking_id)


@require_POST
@dashboard_admin_required
def booking_reassign(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related('worker', 'branch'), id=booking_id,
    )
    new_worker_id = request.POST.get('new_worker_id', '').strip()

    if booking.status != BookingStatus.CONFIRMED:
        messages.error(request, 'Only confirmed bookings can be reassigned.')
        return redirect('dashboard:booking_detail', booking_id=booking_id)

    try:
        new_worker = Worker.objects.get(id=new_worker_id, branch=booking.branch, is_active=True)
    except Worker.DoesNotExist:
        messages.error(request, 'Invalid therapist selected.')
        return redirect('dashboard:booking_detail', booking_id=booking_id)

    old_worker_name = booking.worker.name
    booking.worker = new_worker
    booking.save(update_fields=['worker', 'updated_at'])

    BookingStatusLog.objects.create(
        booking=booking,
        from_status=booking.status,
        to_status=booking.status,
        changed_by=request.user.username,
        reason=f'Therapist reassigned from {old_worker_name} to {new_worker.name}',
    )
    try:
        send_booking_reassigned(booking, old_worker_name=old_worker_name)
    except Exception:
        logger.exception('Reassignment email failed for booking %s', booking_id)

    messages.success(request, f'Therapist changed from {old_worker_name} to {new_worker.name}.')
    return redirect('dashboard:booking_detail', booking_id=booking_id)


# ─────────────────────────────────────────────────────────────────────────────
# Manual Booking
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_admin_required
def manual_booking(request):
    branches = Branch.objects.filter(is_active=True)
    workers  = Worker.objects.filter(is_active=True).select_related('branch')
    services = Service.objects.filter(is_active=True).prefetch_related('branches')

    if request.method == 'POST':
        guest_name   = request.POST.get('guest_name', '').strip()
        guest_phone  = request.POST.get('guest_phone', '').strip()
        guest_email  = request.POST.get('guest_email', '').strip()
        branch_id    = request.POST.get('branch_id', '')
        service_id   = request.POST.get('service_id', '')
        worker_id    = request.POST.get('worker_id', '')
        booking_date = request.POST.get('booking_date', '')
        start_time   = request.POST.get('start_time', '')
        notes        = request.POST.get('notes', '').strip()

        errors = []
        if not guest_name:   errors.append('Guest name is required.')
        if not guest_phone:  errors.append('Guest phone is required.')
        if not booking_date: errors.append('Date is required.')
        if not start_time:   errors.append('Start time is required.')

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            try:
                branch  = Branch.objects.get(id=branch_id)
                service = Service.objects.get(id=service_id)
                worker  = Worker.objects.get(id=worker_id)

                guest, _ = Guest.objects.get_or_create(
                    phone=guest_phone,
                    defaults={'name': guest_name, 'email': guest_email},
                )
                if guest.name != guest_name:
                    guest.name = guest_name
                    guest.save(update_fields=['name'])

                from django.utils.dateparse import parse_date, parse_time
                from apps.bookings.engine import _add_minutes

                bdate = parse_date(booking_date)
                stime = parse_time(start_time)
                etime = _add_minutes(stime, service.duration_minutes)

                # Backend Safety Check: Ensure slot is still available
                from apps.bookings.models import BookingStatus
                conflicts = Booking.objects.filter(
                    worker=worker,
                    booking_date=bdate,
                    start_time__lt=etime,
                    end_time__gt=stime
                ).exclude(status__in=[BookingStatus.CANCELLED, BookingStatus.EXPIRED])

                if conflicts.exists():
                    messages.error(request, f'Conflict detected: {worker.name} is no longer available at {start_time} on this date.')
                    return render(request, 'dashboard/manual_booking.html', {
                        'branches': branches, 'workers': workers, 'services': services,
                        'today': date.today().isoformat(), 'page': 'manual',
                        'post_branch_id': branch_id, 'post_service_id': service_id, 'post_worker_id': worker_id
                    })

                booking = Booking.objects.create(
                    branch=branch, service=service, worker=worker, guest=guest,
                    booking_date=bdate, start_time=stime, end_time=etime,
                    duration_minutes=service.duration_minutes,
                    status=BookingStatus.CONFIRMED,
                    payment_status=PaymentStatus.WAIVED,
                    amount_paid=Decimal('0'),
                    is_manual=True,
                    notes=notes,
                )
                BookingStatusLog.objects.create(
                    booking=booking,
                    from_status=BookingStatus.PENDING_PAYMENT,
                    to_status=BookingStatus.CONFIRMED,
                    changed_by=request.user.username,
                    reason='Manual booking — payment waived',
                )
                try:
                    from apps.notifications.emails import send_booking_confirmed
                    send_booking_confirmed(booking)
                except Exception:
                    pass

                messages.success(request, f'Manual booking created: #{str(booking.id)[:8].upper()}')
                return redirect('dashboard:booking_detail', booking_id=booking.id)

            except Exception as exc:
                logger.exception('Manual booking failed: %s', exc)
                messages.error(request, f'Failed to create booking: {exc}')

    return render(request, 'dashboard/manual_booking.html', {
        'branches':       branches,
        'workers':        workers,
        'services':       services,
        'today':          date.today().isoformat(),
        'page':           'manual',
        'post_branch_id': request.POST.get('branch_id', ''),
        'post_service_id': request.POST.get('service_id', ''),
        'post_worker_id': request.POST.get('worker_id', ''),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Revenue API
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_admin_required
def revenue_data(request):
    today  = date.today()
    months = []
    for i in range(5, -1, -1):
        year  = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year  -= 1
        total = (
            Booking.objects
            .filter(booking_date__year=year, booking_date__month=month, status=BookingStatus.CONFIRMED)
            .aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        )
        months.append({
            'label':   date(year, month, 1).strftime('%b %Y'),
            'revenue': float(total),
            'count':   Booking.objects.filter(
                booking_date__year=year, booking_date__month=month, status=BookingStatus.CONFIRMED,
            ).count(),
        })
    return JsonResponse({'months': months})
