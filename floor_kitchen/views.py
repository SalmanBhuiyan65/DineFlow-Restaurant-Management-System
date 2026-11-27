"""Views for Floor Map, Table Sessions, Order Entry, and Kitchen Display (Member 1: Salman)."""

from collections import defaultdict
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import get_live_kpi_context
from billing_analytics.services import get_or_create_bill
from bookings_menu.models import Customer, DiningTable, MenuItem
from floor_kitchen.models import KitchenTicket, OrderItem, TableSession


def _build_floor_context(selected_table_id=None):
    """Build shared context for the Floor Map and its live-polling partial."""
    tables = list(DiningTable.objects.all())
    active_sessions = {
        s.table_id: s
        for s in TableSession.objects.filter(is_active=True)
        .select_related('table', 'waiter')
        .prefetch_related('order_items__menu_item', 'kitchen_tickets')
    }

    table_cards = []
    for table in tables:
        session = active_sessions.get(table.pk)
        table_cards.append(
            {
                'table': table,
                'session': session,
                'order_count': session.order_items.count() if session else 0,
                'subtotal': session.subtotal if session else 0,
            }
        )

    selected_table = None
    selected_session = None
    if selected_table_id:
        selected_table = DiningTable.objects.filter(pk=selected_table_id).first()
    if selected_table is None and tables:
        selected_table = next(
            (t for t in tables if t.pk in active_sessions),
            tables[0],
        )
    if selected_table:
        selected_session = active_sessions.get(selected_table.pk)

    context = {
        'table_cards': table_cards,
        'selected_table': selected_table,
        'selected_session': selected_session,
        'customers': Customer.objects.all(),
        'menu_items': MenuItem.objects.filter(is_available=True).select_related('category'),
    }
    context.update(get_live_kpi_context())
    return context


@login_required
def floor_dashboard(request):
    """Render the interactive Floor Map & Table Session dashboard (DF-01)."""
    table_id = request.GET.get('table')
    context = _build_floor_context(selected_table_id=table_id)
    context['active_tab'] = 'floor'
    return render(request, 'floor_kitchen/floor_dashboard.html', context)


@login_required
def orders_dashboard(request):
    """Render the dedicated Order Entry & Modification dashboard (DF-02)."""
    table_id = request.GET.get('table')
    context = _build_floor_context(selected_table_id=table_id)
    context['active_tab'] = 'orders'
    return render(request, 'floor_kitchen/orders_dashboard.html', context)


@login_required
def floor_partial(request):
    """Return the Floor grid partial for 4-second live polling."""
    table_id = request.GET.get('table')
    context = _build_floor_context(selected_table_id=table_id)
    return render(request, 'floor_kitchen/_floor_grid.html', context)


@login_required
@require_POST
def seat_table(request, table_id):
    """Start a new TableSession on an empty or reserved DiningTable."""
    table = get_object_or_404(DiningTable, pk=table_id)
    if TableSession.objects.filter(table=table, is_active=True).exists():
        messages.warning(request, f'{table.code} already has an active session.')
        return redirect(f'/?table={table.pk}')

    guest_name = request.POST.get('guest_name', '').strip() or 'Walk-in Guest'
    customer_id = request.POST.get('customer_id') or None
    customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
    if customer and guest_name == 'Walk-in Guest':
        guest_name = customer.name
    try:
        guest_count = max(1, int(request.POST.get('guest_count', table.capacity)))
    except ValueError:
        guest_count = table.capacity

    with transaction.atomic():
        TableSession.objects.create(
            table=table,
            customer=customer,
            guest_name=guest_name,
            guest_count=guest_count,
            waiter=request.user,
            is_active=True,
        )
        table.status = DiningTable.STATUS_ORDERING
        table.save(update_fields=['status'])

    messages.success(request, f'Seated {guest_name} ({guest_count} guests) at {table.code}.')
    return redirect(f'/?table={table.pk}')


@login_required
@require_POST
def add_order_item(request, session_id):
    """Add or increment a MenuItem on an active TableSession (DF-02)."""
    session = get_object_or_404(TableSession, pk=session_id, is_active=True)
    menu_item = get_object_or_404(MenuItem, pk=request.POST.get('menu_item_id'))
    try:
        quantity = max(1, int(request.POST.get('quantity', 1)))
    except ValueError:
        quantity = 1
    special_note = request.POST.get('special_note', '').strip()

    OrderItem.objects.create(
        session=session,
        menu_item=menu_item,
        quantity=quantity,
        unit_price=menu_item.selling_price,
        unit_cost=menu_item.prep_cost,
        special_note=special_note,
        status=OrderItem.STATUS_DRAFT,
    )
    if session.table.status == DiningTable.STATUS_EMPTY:
        session.table.status = DiningTable.STATUS_ORDERING
        session.table.save(update_fields=['status'])

    messages.success(request, f'Added {quantity}x {menu_item.name} to {session.table.code}.')
    referer = request.META.get('HTTP_REFERER', '')
    if '/orders/' in referer:
        return redirect(f'/orders/?table={session.table_id}')
    return redirect(f'/?table={session.table_id}')


@login_required
@require_POST
def remove_order_item(request, item_id):
    """Remove a draft OrderItem from a session before it is bumped."""
    item = get_object_or_404(OrderItem, pk=item_id)
    table_id = item.session.table_id
    if item.status == OrderItem.STATUS_BUMPED:
        messages.warning(request, 'Cannot remove an item already prepared by the kitchen.')
    else:
        item.delete()
        messages.info(request, f'Removed {item.menu_item.name}.')
    referer = request.META.get('HTTP_REFERER', '')
    if '/orders/' in referer:
        return redirect(f'/orders/?table={table_id}')
    return redirect(f'/?table={table_id}')


@login_required
@require_POST
def send_to_kitchen(request, session_id):
    """Fire all draft OrderItems for a session into a new KitchenTicket (DF-02)."""
    session = get_object_or_404(TableSession, pk=session_id, is_active=True)
    draft_items = list(session.order_items.filter(status=OrderItem.STATUS_DRAFT))
    if not draft_items:
        messages.warning(request, 'No draft items to send to kitchen.')
        return redirect(f'/?table={session.table_id}')

    with transaction.atomic():
        ticket_seq = KitchenTicket.objects.count() + 101
        notes = '; '.join(
            f'{item.quantity}x {item.menu_item.name}'
            + (f' ({item.special_note})' if item.special_note else '')
            for item in draft_items
        )
        ticket = KitchenTicket.objects.create(
            session=session,
            ticket_number=f'K-{ticket_seq}',
            status=KitchenTicket.STATUS_QUEUED,
            notes=notes,
        )
        session.order_items.filter(status=OrderItem.STATUS_DRAFT).update(
            status=OrderItem.STATUS_SENT
        )
        session.table.status = DiningTable.STATUS_COOKING
        session.table.save(update_fields=['status'])

    messages.success(request, f'Sent {ticket.ticket_number} for {session.table.code} to Kitchen.')
    return redirect(f'/?table={session.table_id}')


@login_required
@require_POST
def request_bill(request, session_id):
    """Mark table as bill_requested and generate/recalculate its Bill."""
    session = get_object_or_404(TableSession, pk=session_id, is_active=True)
    bill = get_or_create_bill(session)
    session.table.status = DiningTable.STATUS_BILL_REQUESTED
    session.table.save(update_fields=['status'])
    messages.success(request, f'Bill #{bill.pk} ready for {session.table.code}.')
    return redirect('billing_analytics:billing_dashboard')


def _build_kitchen_context():
    """Build oldest-first ticket queue and remaining portion totals (DF-03)."""
    queued_tickets = list(
        KitchenTicket.objects.filter(status=KitchenTicket.STATUS_QUEUED)
        .select_related('session__table')
        .prefetch_related('session__order_items__menu_item')
        .order_by('created_at')
    )
    recently_bumped = list(
        KitchenTicket.objects.filter(status=KitchenTicket.STATUS_BUMPED)
        .select_related('session__table')
        .order_by('-bumped_at')[:6]
    )

    remaining_portions = defaultdict(int)
    for ticket in queued_tickets:
        for item in ticket.session.order_items.filter(status=OrderItem.STATUS_SENT):
            remaining_portions[item.menu_item.name] += item.quantity

    context = {
        'queued_tickets': queued_tickets,
        'recently_bumped': recently_bumped,
        'remaining_portions': sorted(
            remaining_portions.items(),
            key=lambda pair: (-pair[1], pair[0]),
        ),
    }
    context.update(get_live_kpi_context())
    return context


@login_required
def kitchen_display(request):
    """Render the Kitchen Display System (KDS) oldest-first queue (DF-03)."""
    context = _build_kitchen_context()
    context['active_tab'] = 'kitchen'
    return render(request, 'floor_kitchen/kitchen_display.html', context)


@login_required
def kitchen_partial(request):
    """Return KDS ticket board partial for 4-second live polling."""
    context = _build_kitchen_context()
    return render(request, 'floor_kitchen/_kitchen_board.html', context)


@login_required
@require_POST
def bump_ticket(request, ticket_id):
    """Bump a queued KitchenTicket, updating Floor status and remaining portions."""
    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    if ticket.status == KitchenTicket.STATUS_BUMPED:
        messages.info(request, f'{ticket.ticket_number} was already bumped.')
        return redirect('floor_kitchen:kitchen_display')

    with transaction.atomic():
        ticket.status = KitchenTicket.STATUS_BUMPED
        ticket.bumped_at = timezone.now()
        ticket.save(update_fields=['status', 'bumped_at'])

        session = ticket.session
        session.order_items.filter(status=OrderItem.STATUS_SENT).update(
            status=OrderItem.STATUS_BUMPED
        )

        has_other_queued = KitchenTicket.objects.filter(
            session=session,
            status=KitchenTicket.STATUS_QUEUED,
        ).exists()
        if not has_other_queued and session.table.status in (
            DiningTable.STATUS_COOKING,
            DiningTable.STATUS_LATE,
        ):
            session.table.status = DiningTable.STATUS_EATING
            session.table.save(update_fields=['status'])

    messages.success(
        request,
        f'Bumped {ticket.ticket_number} ({session.table.code}). Floor updated to Eating.',
    )
    return redirect('floor_kitchen:kitchen_display')
