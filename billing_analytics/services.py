"""Domain services for Partial/Due Billing, Menu Engineering, and Yearly P&L (Hasibul)."""

from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from billing_analytics.models import (
    Bill,
    HistoricalDailySummary,
    MonthlyFinancialSummary,
    Payment,
)
from bookings_menu.models import DiningTable, MenuItem
from floor_kitchen.models import OrderItem


def get_or_create_bill(session):
    """Return a recalculated Bill for the given TableSession."""
    bill, _ = Bill.objects.get_or_create(session=session)
    if bill.status in (Bill.STATUS_OPEN, Bill.STATUS_PARTIAL):
        bill.recalculate()
    return bill


def record_bill_payment(
    bill_id,
    method,
    recorded_by=None,
    amount=None,
    reference_note='',
    keep_due=False,
):
    """Record a full, split, or partial payment on a Bill.

    Supports multiple split/partial payments on the same Bill. Rejects
    payments on already-paid bills or overpayments exceeding ``due_amount``.
    When ``keep_due=True`` on a partial payment, vacates the table and keeps
    the remaining ``due_amount`` on the customer's profile.

    Args:
        bill_id: Primary key of the target ``Bill``.
        method: Payment method (``cash``, ``card``, or ``bkash``).
        recorded_by: Optional ``User`` recording the payment.
        amount: Optional ``Decimal`` amount (defaults to full remaining due).
        reference_note: Optional receipt or transaction reference.
        keep_due: If True on a partial payment, closes table session as Partial/Due.

    Returns:
        Tuple of ``(Payment_or_None, created_bool)``.
    """
    valid_methods = {c[0] for c in Payment.METHOD_CHOICES}
    if method not in valid_methods:
        raise ValueError(f'Unsupported payment method: {method}')

    with transaction.atomic():
        bill = (
            Bill.objects.select_for_update()
            .select_related('session__table', 'customer')
            .get(pk=bill_id)
        )

        if bill.status == Bill.STATUS_PAID or bill.due_amount <= Decimal('0.00'):
            if bill.payments.exists():
                return bill.payments.first(), False

        if bill.status == Bill.STATUS_OPEN:
            bill.recalculate()

        remaining = bill.due_amount
        if remaining <= Decimal('0.00'):
            return bill.payments.first(), False

        pay_amount = Decimal(amount) if amount is not None else remaining
        pay_amount = pay_amount.quantize(Decimal('0.01'))
        if pay_amount <= Decimal('0.00'):
            raise ValueError('Payment amount must be greater than zero.')
        if pay_amount > remaining:
            raise ValueError(
                f'Payment ৳{pay_amount} exceeds remaining due ৳{remaining}.'
            )

        now = timezone.now()
        payment = Payment.objects.create(
            bill=bill,
            method=method,
            amount=pay_amount,
            reference_note=reference_note,
            recorded_by=recorded_by,
            recorded_at=now,
        )

        bill.paid_amount = (bill.paid_amount or Decimal('0.00')) + pay_amount
        bill.due_amount = max(Decimal('0.00'), bill.total - bill.paid_amount)

        if bill.due_amount == Decimal('0.00'):
            bill.status = Bill.STATUS_PAID
            bill.paid_at = now
            should_vacate = True
        else:
            bill.status = Bill.STATUS_PARTIAL
            should_vacate = keep_due

        bill.save(update_fields=['paid_amount', 'due_amount', 'status', 'paid_at'])

        if should_vacate:
            session = bill.session
            if session.is_active:
                session.is_active = False
                session.ended_at = now
                session.save(update_fields=['is_active', 'ended_at'])
            table = session.table
            if table.status != DiningTable.STATUS_EMPTY:
                table.status = DiningTable.STATUS_EMPTY
                table.save(update_fields=['status'])

        return payment, True


def compute_menu_engineering(days=30, category_id=None):
    """Classify menu items into Stars, Plowhorses, Puzzles, and Dogs."""
    since = timezone.now() - timedelta(days=days)
    items_qs = MenuItem.objects.select_related('category').all()
    if category_id:
        items_qs = items_qs.filter(category_id=category_id)

    order_qs = (
        OrderItem.objects.filter(created_at__gte=since)
        .values('menu_item_id')
        .annotate(total_qty=Sum('quantity'))
    )
    qty_map = {row['menu_item_id']: row['total_qty'] or 0 for row in order_qs}

    rows = []
    for item in items_qs:
        vol = qty_map.get(item.pk, 0)
        margin = float(item.margin)
        rows.append(
            {
                'id': item.pk,
                'name': item.name,
                'category': item.category.name,
                'image_path': item.image_path,
                'selling_price': float(item.selling_price),
                'prep_cost': float(item.prep_cost),
                'margin': round(margin, 2),
                'volume': vol,
                'revenue': round(float(item.selling_price) * vol, 2),
            }
        )

    avg_vol = (sum(r['volume'] for r in rows) / len(rows)) if rows else 0.0
    avg_margin = (sum(r['margin'] for r in rows) / len(rows)) if rows else 0.0
    counts = {'Star': 0, 'Plowhorse': 0, 'Puzzle': 0, 'Dog': 0}

    for row in rows:
        high_vol = row['volume'] >= avg_vol
        high_margin = row['margin'] >= avg_margin
        if high_vol and high_margin:
            quad = 'Star'
        elif high_vol and not high_margin:
            quad = 'Plowhorse'
        elif not high_vol and high_margin:
            quad = 'Puzzle'
        else:
            quad = 'Dog'
        row['quadrant'] = quad
        counts[quad] += 1

    return {
        'items': rows,
        'avg_volume': round(avg_vol, 2),
        'avg_margin': round(avg_margin, 2),
        'quadrant_counts': counts,
    }


def compute_yearly_pnl():
    """Return 12-month Yearly Profit & Loss series (Revenue, Expenses, Net Profit)."""
    summaries = list(MonthlyFinancialSummary.objects.all())
    labels = [s.label for s in summaries]
    revenues = [float(s.revenue) for s in summaries]
    expenses = [float(s.total_expenses) for s in summaries]
    net_profits = [float(s.net_profit) for s in summaries]

    total_rev = sum(revenues)
    total_exp = sum(expenses)
    total_net = sum(net_profits)

    return {
        'labels': labels,
        'revenues': revenues,
        'expenses': expenses,
        'net_profits': net_profits,
        'total_revenue': round(total_rev, 2),
        'total_expenses': round(total_exp, 2),
        'total_net_profit': round(total_net, 2),
    }


def compute_takings_summary(target_date=None):
    """Compute daily takings, hourly breakdown, and previous-day comparison."""
    day = target_date or timezone.localdate()
    payments = Payment.objects.filter(recorded_at__date=day).select_related(
        'bill__session'
    )

    total_sales = Decimal('0.00')
    method_totals = {
        'cash': Decimal('0.00'),
        'card': Decimal('0.00'),
        'bkash': Decimal('0.00'),
    }
    hourly = {f'{h:02d}:00': 0.0 for h in range(12, 24)}
    seen_sessions = set()
    guests_served = 0

    for pay in payments:
        total_sales += pay.amount
        method_totals[pay.method] = (
            method_totals.get(pay.method, Decimal('0.00')) + pay.amount
        )
        local_dt = timezone.localtime(pay.recorded_at)
        hour_key = f'{local_dt.hour:02d}:00'
        if hour_key not in hourly:
            hourly[hour_key] = 0.0
        hourly[hour_key] = round(hourly[hour_key] + float(pay.amount), 2)
        if pay.bill.session_id not in seen_sessions:
            seen_sessions.add(pay.bill.session_id)
            guests_served += pay.bill.session.guest_count

    table_turns = len(seen_sessions)
    spend_per_guest = (
        (total_sales / guests_served).quantize(Decimal('0.01'))
        if guests_served > 0
        else Decimal('0.00')
    )

    prev_summary = HistoricalDailySummary.objects.filter(
        service_date__lt=day
    ).first()
    prev_sales = prev_summary.total_sales if prev_summary else Decimal('0.00')
    sales_delta = total_sales - prev_sales
    delta_pct = (
        round(float((sales_delta / prev_sales) * 100), 1)
        if prev_sales > 0
        else 0.0
    )

    return {
        'service_date': day,
        'total_sales': total_sales,
        'guests_served': guests_served,
        'spend_per_guest': spend_per_guest,
        'table_turns': table_turns,
        'method_totals': method_totals,
        'hourly_labels': list(hourly.keys()),
        'hourly_values': list(hourly.values()),
        'prev_summary': prev_summary,
        'sales_delta': sales_delta,
        'delta_pct': delta_pct,
    }
