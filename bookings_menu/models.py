"""Models for Reservations, Walk-in Waitlist, and Menu Catalog (Member 2: Orin)."""

from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Customer(models.Model):
    """Represents a restaurant customer for visit, order, and due tracking."""

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=25, unique=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    @property
    def total_visits(self):
        """Return total dining sessions linked to this customer."""
        return self.sessions.count()

    @property
    def total_spent(self):
        """Return total amount actually paid across all bills."""
        agg = self.bills.aggregate(total=Sum('paid_amount'))
        return agg['total'] or Decimal('0.00')

    @property
    def due_balance(self):
        """Return total outstanding unpaid due balance across partial/due bills."""
        agg = self.bills.filter(
            status='partial', due_amount__gt=0
        ).aggregate(total=Sum('due_amount'))
        return agg['total'] or Decimal('0.00')

    def __str__(self):
        """Return customer name and phone number."""
        return f'{self.name} ({self.phone})'


class MenuCategory(models.Model):
    """Represents a menu section such as Starters, Mains, or Beverages."""

    name = models.CharField(max_length=60, unique=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Menu Categories'

    def __str__(self):
        """Return category name."""
        return self.name


class MenuItem(models.Model):
    """Represents a dish or beverage on the restaurant menu.

    Computes unit profit margin from ``selling_price - prep_cost`` for
    Menu Engineering Analytics.
    """

    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.CASCADE,
        related_name='items',
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    prep_cost = models.DecimalField(max_digits=8, decimal_places=2)
    selling_price = models.DecimalField(max_digits=8, decimal_places=2)
    is_available = models.BooleanField(default=True)
    prep_time_minutes = models.PositiveIntegerField(default=10)
    image_path = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['category__display_order', 'name']

    @property
    def margin(self):
        """Return unit profit margin as a Decimal."""
        return (self.selling_price or Decimal('0.00')) - (
            self.prep_cost or Decimal('0.00')
        )

    def __str__(self):
        """Return dish name and selling price."""
        return f'{self.name} (৳{self.selling_price})'


class DiningTable(models.Model):
    """Represents a physical dining table on the restaurant floor."""

    STATUS_EMPTY = 'empty'
    STATUS_RESERVED = 'reserved'
    STATUS_ORDERING = 'ordering'
    STATUS_COOKING = 'cooking'
    STATUS_EATING = 'eating'
    STATUS_LATE = 'late'
    STATUS_BILL_REQUESTED = 'bill_requested'

    STATUS_CHOICES = [
        (STATUS_EMPTY, 'Empty'),
        (STATUS_RESERVED, 'Reserved'),
        (STATUS_ORDERING, 'Ordering'),
        (STATUS_COOKING, 'Cooking'),
        (STATUS_EATING, 'Eating'),
        (STATUS_LATE, 'Late'),
        (STATUS_BILL_REQUESTED, 'Bill Requested'),
    ]

    code = models.CharField(max_length=10, unique=True)
    capacity = models.PositiveIntegerField()
    zone = models.CharField(max_length=40, default='Main Hall')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_EMPTY,
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        """Return table code and seating capacity."""
        return f'{self.code} ({self.capacity} seats)'


class Reservation(models.Model):
    """Represents a table reservation on the booking timeline."""

    STATUS_BOOKED = 'booked'
    STATUS_SEATED = 'seated'
    STATUS_DONE = 'done'
    STATUS_LATE = 'late'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_BOOKED, 'Booked'),
        (STATUS_SEATED, 'Seated'),
        (STATUS_DONE, 'Done'),
        (STATUS_LATE, 'Late'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    guest_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=25, blank=True)
    party_size = models.PositiveIntegerField()
    table = models.ForeignKey(
        DiningTable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations',
    )
    reserved_for = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_BOOKED,
    )
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['reserved_for']

    def __str__(self):
        """Return guest name, party size, and reservation status."""
        return f'{self.guest_name} (Party of {self.party_size}) - {self.status}'


class WaitlistEntry(models.Model):
    """Represents a walk-in party waiting for a best-fit table."""

    STATUS_WAITING = 'waiting'
    STATUS_SEATED = 'seated'
    STATUS_LEFT = 'left'

    STATUS_CHOICES = [
        (STATUS_WAITING, 'Waiting'),
        (STATUS_SEATED, 'Seated'),
        (STATUS_LEFT, 'Left'),
    ]

    guest_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=25, blank=True)
    party_size = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_WAITING,
    )
    assigned_table = models.ForeignKey(
        DiningTable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='waitlist_assignments',
    )
    estimated_wait_minutes = models.PositiveIntegerField(default=15)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['joined_at']

    def __str__(self):
        """Return waitlist guest and party size."""
        return f'{self.guest_name} ({self.party_size}) - {self.status}'
