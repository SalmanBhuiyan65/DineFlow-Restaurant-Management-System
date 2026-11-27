"""Unit tests for Member 2 (Orin): Reservations, Best-Fit Seating, and Menu Catalog."""

from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings_menu.models import (
    DiningTable,
    MenuCategory,
    MenuItem,
    Reservation,
    WaitlistEntry,
)
from bookings_menu.services import assign_waitlist_best_fit, find_best_fit_table


class BookingsMenuTests(TestCase):
    """Verify normal, boundary, and invalid cases for Orin's 3 features."""

    def setUp(self):
        self.user = User.objects.create_user(username='orin', password='pw')
        self.client.force_login(self.user)
        self.t2 = DiningTable.objects.create(code='T2', capacity=2)
        self.t4 = DiningTable.objects.create(code='T4', capacity=4)
        self.t6 = DiningTable.objects.create(code='T6', capacity=6)
        self.cat = MenuCategory.objects.create(name='Starters')

    def test_best_fit_picks_smallest_suitable_table(self):
        """Normal/Boundary: Party of 3 picks 4-seat table instead of 6-seat table."""
        best = find_best_fit_table(3)
        self.assertEqual(best, self.t4)

    def test_best_fit_returns_none_when_party_too_large(self):
        """Boundary: Party larger than any empty table remains on waitlist."""
        entry = WaitlistEntry.objects.create(guest_name='Big Group', party_size=10)
        assigned = assign_waitlist_best_fit(entry)
        self.assertIsNone(assigned)
        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistEntry.STATUS_WAITING)

    def test_best_fit_invalid_zero_party_size(self):
        """Invalid: Zero or negative party size returns None."""
        self.assertIsNone(find_best_fit_table(0))
        self.assertIsNone(find_best_fit_table(-2))

    def test_create_and_seat_reservation(self):
        """Normal: Creating and seating a reservation creates a TableSession."""
        res = Reservation.objects.create(
            guest_name='Nabila',
            party_size=2,
            table=self.t2,
            reserved_for=timezone.now(),
        )
        self.client.post(reverse('bookings_menu:seat_reservation', args=[res.pk]))
        res.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(res.status, Reservation.STATUS_SEATED)
        self.assertEqual(self.t2.status, DiningTable.STATUS_ORDERING)

    def test_menu_item_margin_and_toggle(self):
        """Normal: MenuItem computes margin and toggles availability."""
        item = MenuItem.objects.create(
            category=self.cat,
            name='Soup',
            prep_cost=Decimal('100.00'),
            selling_price=Decimal('250.00'),
        )
        self.assertEqual(item.margin, Decimal('150.00'))
        self.client.post(reverse('bookings_menu:toggle_menu_item', args=[item.pk]))
        item.refresh_from_db()
        self.assertFalse(item.is_available)
