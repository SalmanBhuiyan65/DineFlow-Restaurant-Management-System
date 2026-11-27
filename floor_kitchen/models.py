"""Models for Floor Map, Table Sessions, Orders, and Kitchen Display (Member 1: Salman)."""

from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from bookings_menu.models import Customer, DiningTable, MenuItem


class TableSession(models.Model):
    """Represents an active or completed dining session at a table."""

    table = models.ForeignKey(
        DiningTable,
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions',
    )
    guest_name = models.CharField(max_length=100, default='Walk-in Guest')
    guest_count = models.PositiveIntegerField(default=2)
    waiter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='served_sessions',
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-started_at']

    @property
    def subtotal(self):
        """Compute total pre-tax order amount for non-cancelled items."""
        return sum(
            (item.line_total for item in self.order_items.all()),
            Decimal('0.00'),
        )

    @property
    def elapsed_minutes(self):
        """Return integer minutes since the session started."""
        end = self.ended_at or timezone.now()
        delta = end - self.started_at
        return max(0, int(delta.total_seconds() // 60))

    def __str__(self):
        """Return table code and guest name."""
        return f'{self.table.code} - {self.guest_name} ({self.guest_count})'


class OrderItem(models.Model):
    """Represents a single line item ordered during a TableSession."""

    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_BUMPED = 'bumped'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENT, 'Sent to Kitchen'),
        (STATUS_BUMPED, 'Prepared / Bumped'),
    ]

    session = models.ForeignKey(
        TableSession,
        on_delete=models.CASCADE,
        related_name='order_items',
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        related_name='order_lines',
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2)
    special_note = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def line_total(self):
        """Return selling price multiplied by quantity."""
        return self.unit_price * self.quantity

    @property
    def line_margin(self):
        """Return total profit margin for this order line."""
        return (self.unit_price - self.unit_cost) * self.quantity

    def __str__(self):
        """Return quantity and menu item name."""
        return f'{self.quantity}x {self.menu_item.name}'


class KitchenTicket(models.Model):
    """Represents an oldest-first kitchen preparation ticket for a table."""

    LATE_THRESHOLD_MINUTES = 12
    STATUS_QUEUED = 'queued'
    STATUS_BUMPED = 'bumped'

    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_BUMPED, 'Bumped'),
    ]

    session = models.ForeignKey(
        TableSession,
        on_delete=models.CASCADE,
        related_name='kitchen_tickets',
    )
    ticket_number = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    bumped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    @property
    def elapsed_minutes(self):
        """Return elapsed minutes since ticket was fired to kitchen."""
        end = self.bumped_at or timezone.now()
        delta = end - self.created_at
        return max(0, int(delta.total_seconds() // 60))

    @property
    def is_late(self):
        """Return True if queued ticket has exceeded the 12-minute SLA."""
        return (
            self.status == self.STATUS_QUEUED
            and self.elapsed_minutes >= self.LATE_THRESHOLD_MINUTES
        )

    def __str__(self):
        """Return ticket number and table code."""
        return f'{self.ticket_number} ({self.session.table.code})'
