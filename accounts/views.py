"""Views for staff authentication and 1-click demo role switching."""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import StaffProfile
from billing_analytics.models import Payment
from bookings_menu.models import DiningTable, WaitlistEntry
from floor_kitchen.models import KitchenTicket, TableSession


def get_live_kpi_context():
    """Return shared live dinner-service KPIs for the top navigation bar."""
    today = timezone.localdate()
    today_payments = Payment.objects.filter(recorded_at__date=today)
    today_sales = sum(p.amount for p in today_payments)
    active_sessions = TableSession.objects.filter(is_active=True)
    seated_guests = sum(s.guest_count for s in active_sessions)
    waiting_parties = WaitlistEntry.objects.filter(
        status=WaitlistEntry.STATUS_WAITING
    ).count()
    late_tickets = [
        t
        for t in KitchenTicket.objects.filter(status=KitchenTicket.STATUS_QUEUED)
        if t.is_late
    ]
    late_tables = DiningTable.objects.filter(
        status=DiningTable.STATUS_LATE
    ).count()
    urgent_alerts = len(late_tickets) + late_tables

    return {
        'kpi_sales': today_sales,
        'kpi_seated_guests': seated_guests,
        'kpi_waiting_tables': waiting_parties,
        'kpi_urgent_alerts': urgent_alerts,
        'kpi_late_tickets': late_tickets,
    }


def login_view(request):
    """Render and handle staff login."""
    if request.user.is_authenticated:
        return redirect('floor_kitchen:floor_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('floor_kitchen:floor_dashboard')
        messages.error(request, 'Invalid staff username or password.')

    demo_profiles = StaffProfile.objects.select_related('user').all()
    return render(
        request,
        'accounts/login.html',
        {'demo_profiles': demo_profiles},
    )


def logout_view(request):
    """Log out the current staff member."""
    logout(request)
    return redirect('accounts:login')


@require_POST
def switch_role(request, role):
    """Switch active session to a pre-seeded demo staff account by role."""
    profile = StaffProfile.objects.filter(role=role).select_related('user').first()
    if profile is None:
        user = User.objects.filter(is_superuser=True).first()
        if user is None:
            messages.error(request, 'No demo account found. Run seed_dineflow first.')
            return redirect('accounts:login')
    else:
        user = profile.user

    login(request, user)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)
