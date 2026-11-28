"""Views for Billing, Partial/Due Payments, Menu Analytics, and P&L (Member 3: Hasibul)."""

import json
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.views import get_live_kpi_context
from billing_analytics.models import Bill
from billing_analytics.services import (
    compute_menu_engineering,
    compute_takings_summary,
    compute_yearly_pnl,
    get_or_create_bill,
    record_bill_payment,
)
from bookings_menu.models import Customer, MenuCategory
from floor_kitchen.models import TableSession


@login_required
def billing_dashboard(request):
    """Render itemized Billing, Partial/Split Payments, and Due Balances."""
    for session in TableSession.objects.filter(is_active=True):
        if session.order_items.exists():
            get_or_create_bill(session)

    open_bills = (
        Bill.objects.filter(status=Bill.STATUS_OPEN)
        .select_related('session__table', 'customer')
        .prefetch_related('session__order_items__menu_item', 'payments')
        .order_by('-created_at')
    )
    due_bills = (
        Bill.objects.filter(status=Bill.STATUS_PARTIAL, due_amount__gt=0)
        .select_related('session__table', 'customer')
        .prefetch_related('payments')
        .order_by('-created_at')
    )
    paid_bills = (
        Bill.objects.filter(status=Bill.STATUS_PAID)
        .select_related('session__table', 'customer')
        .prefetch_related('payments')
        .order_by('-paid_at')[:10]
    )

    context = {
        'active_tab': 'billing',
        'open_bills': open_bills,
        'due_bills': due_bills,
        'paid_bills': paid_bills,
        'customers': Customer.objects.all(),
    }
    context.update(get_live_kpi_context())
    return render(request, 'billing_analytics/billing_dashboard.html', context)


@login_required
def print_bill(request, bill_id):
    """Render a clean printable itemized receipt for a Bill."""
    bill = get_object_or_404(
        Bill.objects.select_related('session__table', 'customer').prefetch_related(
            'session__order_items__menu_item', 'payments'
        ),
        pk=bill_id,
    )
    if bill.status == Bill.STATUS_OPEN:
        bill.recalculate()
    return render(request, 'billing_analytics/print_bill.html', {'bill': bill})


@login_required
@require_POST
def pay_bill(request, bill_id):
    """Record full, split, or partial Cash/Card/bKash payment on a Bill."""
    method = request.POST.get('method', 'cash')
    reference_note = request.POST.get('reference_note', '').strip()
    keep_due = request.POST.get('keep_due') == '1'

    customer_id = request.POST.get('customer_id') or None
    if customer_id:
        bill_obj = get_object_or_404(Bill, pk=bill_id)
        customer = Customer.objects.filter(pk=customer_id).first()
        if customer:
            bill_obj.customer = customer
            bill_obj.save(update_fields=['customer'])
            if bill_obj.session.customer_id is None:
                bill_obj.session.customer = customer
                bill_obj.session.save(update_fields=['customer'])

    raw_amount = request.POST.get('amount', '').strip()
    amount = None
    if raw_amount:
        try:
            amount = Decimal(raw_amount)
        except InvalidOperation:
            messages.error(request, 'Invalid payment amount entered.')
            return redirect('billing_analytics:billing_dashboard')

    try:
        payment, created = record_bill_payment(
            bill_id=bill_id,
            method=method,
            recorded_by=request.user,
            amount=amount,
            reference_note=reference_note,
            keep_due=keep_due,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('billing_analytics:billing_dashboard')

    if created:
        bill = payment.bill
        if bill.due_amount > Decimal('0.00'):
            messages.success(
                request,
                f'Recorded partial {payment.get_method_display()} payment of ৳{payment.amount}. '
                f'Remaining Due: ৳{bill.due_amount}.',
            )
        else:
            messages.success(
                request,
                f'Recorded {payment.get_method_display()} payment of ৳{payment.amount}. '
                'Bill settled and table vacated.',
            )
    else:
        messages.warning(
            request,
            f'Bill #{bill_id} was already paid in full. Duplicate payment ignored.',
        )
    return redirect('billing_analytics:billing_dashboard')


@login_required
def menu_analytics(request):
    """Render Yearly P&L Line Graph and Menu Engineering Matrix."""
    try:
        days = int(request.GET.get('days', 30))
    except ValueError:
        days = 30
    category_id = request.GET.get('category') or None
    if category_id:
        try:
            category_id = int(category_id)
        except ValueError:
            category_id = None

    data = compute_menu_engineering(days=days, category_id=category_id)
    pnl_data = compute_yearly_pnl()
    context = {
        'active_tab': 'analytics',
        'categories': MenuCategory.objects.all(),
        'selected_days': days,
        'selected_category': category_id,
        'analytics': data,
        'pnl': pnl_data,
        'chart_json': json.dumps(data),
        'pnl_json': json.dumps(pnl_data),
    }
    context.update(get_live_kpi_context())
    return render(request, 'billing_analytics/menu_analytics.html', context)


@login_required
def takings_report(request):
    """Render Daily Takings & Shift Summary Reports."""
    summary = compute_takings_summary()
    context = {
        'active_tab': 'takings',
        'summary': summary,
        'hourly_labels_json': json.dumps(summary['hourly_labels']),
        'hourly_values_json': json.dumps(summary['hourly_values']),
    }
    context.update(get_live_kpi_context())
    return render(request, 'billing_analytics/takings_report.html', context)
