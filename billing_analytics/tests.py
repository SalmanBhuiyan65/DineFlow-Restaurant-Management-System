"""Unit tests for Hasibul: Partial/Due Billing, Menu Analytics, and Yearly P&L."""

from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase

from billing_analytics.models import MonthlyFinancialSummary, Payment
from billing_analytics.services import (
    compute_menu_engineering,
    compute_takings_summary,
    compute_yearly_pnl,
    get_or_create_bill,
    record_bill_payment,
)
from bookings_menu.models import Customer, DiningTable, MenuCategory, MenuItem
from floor_kitchen.models import OrderItem, TableSession


class BillingAnalyticsTests(TestCase):
    """Verify full, split/partial, due balance, analytics, and P&L logic."""

    def setUp(self):
        self.user = User.objects.create_user(username='hasibul', password='pw')
        self.customer = Customer.objects.create(name='Nabila', phone='01700-000001')
        self.table = DiningTable.objects.create(
            code='T2', capacity=2, status=DiningTable.STATUS_BILL_REQUESTED
        )
        self.cat = MenuCategory.objects.create(name='Grills')
        self.steak = MenuItem.objects.create(
            category=self.cat,
            name='Ribeye',
            prep_cost=Decimal('500.00'),
            selling_price=Decimal('1000.00'),
        )
        self.session = TableSession.objects.create(
            table=self.table,
            customer=self.customer,
            guest_name='Nabila',
            guest_count=2,
        )
        OrderItem.objects.create(
            session=self.session,
            menu_item=self.steak,
            quantity=2,
            unit_price=self.steak.selling_price,
            unit_cost=self.steak.prep_cost,
            status=OrderItem.STATUS_BUMPED,
        )

    def test_idempotent_payment_does_not_double_count_takings(self):
        """Exceptional: Paying an already-settled bill twice ignores the 2nd attempt."""
        bill = get_or_create_bill(self.session)
        self.assertEqual(bill.total, Decimal('2100.00'))

        p1, created1 = record_bill_payment(bill.pk, Payment.METHOD_CASH, self.user)
        p2, created2 = record_bill_payment(bill.pk, Payment.METHOD_CARD, self.user)

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(p1.pk, p2.pk)
        self.assertEqual(Payment.objects.count(), 1)

        self.table.refresh_from_db()
        self.assertEqual(self.table.status, DiningTable.STATUS_EMPTY)

        summary = compute_takings_summary()
        self.assertEqual(summary['total_sales'], Decimal('2100.00'))
        self.assertEqual(summary['table_turns'], 1)

    def test_partial_and_due_settlement_updates_customer_balance(self):
        """Normal: Partial payment stores remaining due on Customer and settles later."""
        bill = get_or_create_bill(self.session)
        record_bill_payment(
            bill.pk,
            Payment.METHOD_CASH,
            self.user,
            amount=Decimal('1000.00'),
            keep_due=True,
        )
        bill.refresh_from_db()
        self.assertEqual(bill.due_amount, Decimal('1100.00'))
        self.assertEqual(self.customer.due_balance, Decimal('1100.00'))
        self.assertEqual(self.customer.total_spent, Decimal('1000.00'))

        record_bill_payment(
            bill.pk,
            Payment.METHOD_BKASH,
            self.user,
            amount=Decimal('1100.00'),
        )
        self.assertEqual(self.customer.due_balance, Decimal('0.00'))
        self.assertEqual(self.customer.total_spent, Decimal('2100.00'))

    def test_overpayment_raises_value_error(self):
        """Invalid: Paying more than due_amount raises ValueError."""
        bill = get_or_create_bill(self.session)
        with self.assertRaises(ValueError):
            record_bill_payment(
                bill.pk, Payment.METHOD_CASH, self.user, amount=Decimal('5000.00')
            )

    def test_invalid_payment_method_raises_value_error(self):
        """Invalid: Unsupported payment method raises ValueError."""
        bill = get_or_create_bill(self.session)
        with self.assertRaises(ValueError):
            record_bill_payment(bill.pk, 'crypto', self.user)

    def test_menu_engineering_and_yearly_pnl(self):
        """Normal: Menu engineering classifies quadrants and Yearly P&L computes net."""
        data = compute_menu_engineering(days=30)
        self.assertEqual(data['items'][0]['quadrant'], 'Star')

        MonthlyFinancialSummary.objects.create(
            year=2026,
            month=1,
            label='Jan',
            revenue=Decimal('100000.00'),
            cogs=Decimal('40000.00'),
            operating_expenses=Decimal('35000.00'),
        )
        pnl = compute_yearly_pnl()
        self.assertEqual(pnl['total_net_profit'], 25000.0)
