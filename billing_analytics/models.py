"""Models for Itemized Billing, Partial/Due Payments, and P&L (Member 3: Hasibul)."""

from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from bookings_menu.models import Customer
from floor_kitchen.models import TableSession


class Bill(models.Model):
    """Represents an itemized customer bill supporting full, partial, and due balances."""

    DEFAULT_VAT_RATE = Decimal('0.05')
    STATUS_OPEN = 'open'
    STATUS_PARTIAL = 'partial'
    STATUS_PAID = 'paid'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_PARTIAL, 'Partial / Due'),
        (STATUS_PAID, 'Paid'),
    ]

    session = models.OneToOneField(
        TableSession,
        on_delete=models.CASCADE,
        related_name='bill',
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bills',
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    vat_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=DEFAULT_VAT_RATE,
    )
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    due_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)

    def recalculate(self):
        """Recalculate subtotal, VAT, total, and remaining due_amount."""
        sub = self.session.subtotal
        vat = (sub * self.vat_rate).quantize(Decimal('0.01'))
        total = (sub + vat).quantize(Decimal('0.01'))
        self.subtotal = sub
        self.vat_amount = vat
        self.total = total
        self.due_amount = max(Decimal('0.00'), total - (self.paid_amount or Decimal('0.00')))
        if self.session.customer and self.customer_id is None:
            self.customer = self.session.customer
        self.save(
            update_fields=[
                'subtotal',
                'vat_amount',
                'total',
                'due_amount',
                'customer',
            ]
        )

    def __str__(self):
        """Return bill ID, table code, and total."""
        return f'Bill #{self.pk} ({self.session.table.code}) - ৳{self.total}'


class Payment(models.Model):
    """Represents a full, split, or partial payment toward a Bill."""

    METHOD_CASH = 'cash'
    METHOD_CARD = 'card'
    METHOD_BKASH = 'bkash'

    METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_CARD, 'Card'),
        (METHOD_BKASH, 'bKash'),
    ]

    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_note = models.CharField(max_length=120, blank=True)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_payments',
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        """Return payment method and amount."""
        return f'{self.get_method_display()} ৳{self.amount} for Bill #{self.bill_id}'


class HistoricalDailySummary(models.Model):
    """Stores previous-day takings snapshots for shift comparison."""

    service_date = models.DateField(unique=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2)
    guests_served = models.PositiveIntegerField(default=0)
    table_turns = models.PositiveIntegerField(default=0)
    hourly_breakdown_json = models.JSONField(default=dict)
    payment_breakdown_json = models.JSONField(default=dict)

    class Meta:
        ordering = ['-service_date']

    def __str__(self):
        """Return service date and total sales."""
        return f'{self.service_date}: ৳{self.total_sales}'


class MonthlyFinancialSummary(models.Model):
    """Stores monthly revenue and expenses for the Yearly Profit & Loss graph."""

    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    label = models.CharField(max_length=20)
    revenue = models.DecimalField(max_digits=12, decimal_places=2)
    cogs = models.DecimalField(max_digits=12, decimal_places=2)
    operating_expenses = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['year', 'month']
        unique_together = ('year', 'month')

    @property
    def total_expenses(self):
        """Return combined COGS and operating expenses."""
        return self.cogs + self.operating_expenses

    @property
    def net_profit(self):
        """Return net profit (or loss if negative)."""
        return self.revenue - self.total_expenses

    def __str__(self):
        """Return month label and net profit."""
        return f'{self.label}: Net ৳{self.net_profit}'
