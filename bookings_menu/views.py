"""Views for Reservations, Walk-in Waitlist & Best-Fit, and Menu (Member 2: Orin)."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import get_live_kpi_context
from bookings_menu.models import (
    Customer,
    DiningTable,
    MenuCategory,
    MenuItem,
    Reservation,
    WaitlistEntry,
)
from bookings_menu.services import assign_waitlist_best_fit, find_best_fit_table
from floor_kitchen.models import TableSession


@login_required
def bookings_dashboard(request):
    """Render Reservations & Booking Timeline dashboard (DF-04)."""
    reservations = Reservation.objects.select_related('table').all()
    tables = DiningTable.objects.all()

    context = {
        'active_tab': 'bookings',
        'reservations': reservations,
        'tables': tables,
    }
    context.update(get_live_kpi_context())
    return render(request, 'bookings_menu/bookings_dashboard.html', context)


@login_required
def waitlist_dashboard(request):
    """Render Walk-in Waitlist & Best-Fit Seating dashboard (DF-05)."""
    waitlist = WaitlistEntry.objects.select_related('assigned_table').filter(
        status=WaitlistEntry.STATUS_WAITING
    )
    empty_tables = DiningTable.objects.filter(status=DiningTable.STATUS_EMPTY)

    context = {
        'active_tab': 'waitlist',
        'waitlist': waitlist,
        'empty_tables': empty_tables,
    }
    context.update(get_live_kpi_context())
    return render(request, 'bookings_menu/waitlist_dashboard.html', context)


@login_required
@require_POST
def create_reservation(request):
    """Create a new table reservation (DF-04)."""
    guest_name = request.POST.get('guest_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    notes = request.POST.get('notes', '').strip()
    try:
        party_size = max(1, int(request.POST.get('party_size', 2)))
    except ValueError:
        party_size = 2

    time_str = request.POST.get('reserved_for', '').strip()
    try:
        naive_dt = datetime.strptime(time_str, '%Y-%m-%dT%H:%M')
        reserved_for = timezone.make_aware(naive_dt, timezone.get_current_timezone())
    except ValueError:
        reserved_for = timezone.now()

    table_id = request.POST.get('table_id')
    table = DiningTable.objects.filter(pk=table_id).first() if table_id else None
    if table is None:
        table = find_best_fit_table(party_size)

    Reservation.objects.create(
        guest_name=guest_name or 'Guest',
        phone=phone,
        party_size=party_size,
        table=table,
        reserved_for=reserved_for,
        status=Reservation.STATUS_BOOKED,
        notes=notes,
    )
    if table and table.status == DiningTable.STATUS_EMPTY:
        table.status = DiningTable.STATUS_RESERVED
        table.save(update_fields=['status'])

    messages.success(request, f'Reservation created for {guest_name or "Guest"}.')
    return redirect('bookings_menu:bookings_dashboard')


@login_required
@require_POST
def seat_reservation(request, reservation_id):
    """Seat a booked reservation onto its table or best-fit available table."""
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    table = reservation.table
    if table is None or TableSession.objects.filter(table=table, is_active=True).exists():
        table = find_best_fit_table(reservation.party_size)

    if table is None:
        messages.warning(
            request,
            f'No empty table fits {reservation.party_size} guests right now.',
        )
        return redirect('bookings_menu:bookings_dashboard')

    with transaction.atomic():
        reservation.table = table
        reservation.status = Reservation.STATUS_SEATED
        reservation.save(update_fields=['table', 'status'])

        TableSession.objects.create(
            table=table,
            guest_name=reservation.guest_name,
            guest_count=reservation.party_size,
            waiter=request.user,
            is_active=True,
        )
        table.status = DiningTable.STATUS_ORDERING
        table.save(update_fields=['status'])

    messages.success(
        request,
        f'Seated reservation {reservation.guest_name} at {table.code}.',
    )
    return redirect('bookings_menu:bookings_dashboard')


@login_required
@require_POST
def mark_reservation_status(request, reservation_id, status):
    """Update reservation status to late, done, or cancelled."""
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    allowed = {
        Reservation.STATUS_LATE,
        Reservation.STATUS_DONE,
        Reservation.STATUS_CANCELLED,
    }
    if status in allowed:
        reservation.status = status
        reservation.save(update_fields=['status'])
        if (
            status == Reservation.STATUS_CANCELLED
            and reservation.table
            and reservation.table.status == DiningTable.STATUS_RESERVED
        ):
            reservation.table.status = DiningTable.STATUS_EMPTY
            reservation.table.save(update_fields=['status'])
        messages.info(request, f'Reservation updated to {status}.')
    return redirect('bookings_menu:bookings_dashboard')


@login_required
@require_POST
def add_walkin(request):
    """Add a walk-in party and optionally seat immediately via Best-Fit (DF-05)."""
    guest_name = request.POST.get('guest_name', '').strip() or 'Walk-in Party'
    phone = request.POST.get('phone', '').strip()
    try:
        party_size = max(1, int(request.POST.get('party_size', 2)))
    except ValueError:
        party_size = 2

    entry = WaitlistEntry.objects.create(
        guest_name=guest_name,
        phone=phone,
        party_size=party_size,
        estimated_wait_minutes=10 + party_size * 2,
    )
    auto_seat = request.POST.get('auto_seat') == '1'
    if auto_seat:
        table = assign_waitlist_best_fit(entry)
        if table:
            TableSession.objects.create(
                table=table,
                guest_name=entry.guest_name,
                guest_count=entry.party_size,
                waiter=request.user,
                is_active=True,
            )
            messages.success(
                request,
                f'Best-fit assigned {entry.guest_name} to {table.code} ({table.capacity} seats).',
            )
            return redirect('bookings_menu:waitlist_dashboard')

    messages.info(request, f'Added {guest_name} (party of {party_size}) to waitlist.')
    return redirect('bookings_menu:waitlist_dashboard')


@login_required
@require_POST
def seat_waitlist_entry(request, entry_id):
    """Seat a waiting walk-in party using the Best-Fit Seating algorithm."""
    entry = get_object_or_404(WaitlistEntry, pk=entry_id)
    with transaction.atomic():
        table = assign_waitlist_best_fit(entry)
        if table is None:
            messages.warning(
                request,
                f'No empty table available for {entry.guest_name} ({entry.party_size} guests).',
            )
            return redirect('bookings_menu:waitlist_dashboard')

        TableSession.objects.create(
            table=table,
            guest_name=entry.guest_name,
            guest_count=entry.party_size,
            waiter=request.user,
            is_active=True,
        )

    messages.success(
        request,
        f'Best-fit seated {entry.guest_name} at {table.code} ({table.capacity} seats).',
    )
    return redirect('bookings_menu:waitlist_dashboard')


@login_required
def menu_catalog(request):
    """Render Menu Catalog & Category Management view (DF-06)."""
    categories = MenuCategory.objects.prefetch_related('items').all()
    context = {
        'active_tab': 'menu',
        'categories': categories,
    }
    context.update(get_live_kpi_context())
    return render(request, 'bookings_menu/menu_catalog.html', context)


@login_required
@require_POST
def create_menu_item(request):
    """Create a new dish in the Menu Catalog (DF-06)."""
    category = get_object_or_404(MenuCategory, pk=request.POST.get('category_id'))
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    try:
        prep_cost = Decimal(request.POST.get('prep_cost', '0'))
        selling_price = Decimal(request.POST.get('selling_price', '0'))
    except InvalidOperation:
        messages.error(request, 'Invalid price or prep cost.')
        return redirect('bookings_menu:menu_catalog')

    if not name or selling_price <= 0:
        messages.error(request, 'Dish name and positive selling price are required.')
        return redirect('bookings_menu:menu_catalog')

    MenuItem.objects.create(
        category=category,
        name=name,
        description=description,
        prep_cost=prep_cost,
        selling_price=selling_price,
        is_available=True,
    )
    messages.success(request, f'Added "{name}" to {category.name}.')
    return redirect('bookings_menu:menu_catalog')


@login_required
@require_POST
def toggle_menu_item(request, item_id):
    """Toggle availability of a MenuItem."""
    item = get_object_or_404(MenuItem, pk=item_id)
    item.is_available = not item.is_available
    item.save(update_fields=['is_available'])
    state = 'available' if item.is_available else 'unavailable'
    messages.info(request, f'{item.name} marked as {state}.')
    return redirect('bookings_menu:menu_catalog')


@login_required
def customers_dashboard(request):
    """Render Customer Database, Purchase History, and Due Balances."""
    query = request.GET.get('q', '').strip()
    customers_qs = Customer.objects.prefetch_related(
        'sessions__order_items__menu_item',
        'bills__payments',
    ).all()
    if query:
        customers_qs = customers_qs.filter(name__icontains=query) | customers_qs.filter(
            phone__icontains=query
        )

    context = {
        'active_tab': 'customers',
        'customers': customers_qs.distinct(),
        'search_query': query,
    }
    context.update(get_live_kpi_context())
    return render(request, 'bookings_menu/customers_dashboard.html', context)


@login_required
@require_POST
def create_customer(request):
    """Create a new customer record in the Customer Database."""
    name = request.POST.get('name', '').strip()
    phone = request.POST.get('phone', '').strip()
    email = request.POST.get('email', '').strip()
    if not name or not phone:
        messages.error(request, 'Customer name and phone number are required.')
        return redirect('bookings_menu:customers_dashboard')

    customer, created = Customer.objects.get_or_create(
        phone=phone,
        defaults={'name': name, 'email': email},
    )
    if not created:
        messages.info(request, f'Customer with phone {phone} already exists ({customer.name}).')
    else:
        messages.success(request, f'Added customer {name} ({phone}).')
    return redirect('bookings_menu:customers_dashboard')
