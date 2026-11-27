"""Unit tests for Member 1 (Salman): Floor Map, Order Entry, and KDS."""

from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings_menu.models import DiningTable, MenuCategory, MenuItem
from floor_kitchen.models import KitchenTicket, OrderItem, TableSession


class FloorKitchenTests(TestCase):
    """Verify normal, boundary, and invalid cases for Salman's 3 features."""

    def setUp(self):
        self.user = User.objects.create_user(username='salman', password='pw')
        self.client.force_login(self.user)
        self.table = DiningTable.objects.create(
            code='T1', capacity=4, status=DiningTable.STATUS_EMPTY
        )
        self.cat = MenuCategory.objects.create(name='Mains')
        self.dish = MenuItem.objects.create(
            category=self.cat,
            name='Grilled Chicken',
            prep_cost=Decimal('150.00'),
            selling_price=Decimal('400.00'),
        )

    def test_seat_table_creates_active_session(self):
        """Normal: Seating an empty table starts a session and sets status to ordering."""
        resp = self.client.post(
            reverse('floor_kitchen:seat_table', args=[self.table.pk]),
            {'guest_name': 'Nabila', 'guest_count': 3},
        )
        self.assertEqual(resp.status_code, 302)
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, DiningTable.STATUS_ORDERING)
        self.assertTrue(
            TableSession.objects.filter(table=self.table, is_active=True).exists()
        )

    def test_duplicate_seat_table_rejected(self):
        """Invalid: Seating an already-active table does not create a second session."""
        TableSession.objects.create(table=self.table, guest_name='First', is_active=True)
        self.client.post(
            reverse('floor_kitchen:seat_table', args=[self.table.pk]),
            {'guest_name': 'Second', 'guest_count': 2},
        )
        self.assertEqual(
            TableSession.objects.filter(table=self.table, is_active=True).count(), 1
        )

    def test_send_order_to_kitchen_and_bump(self):
        """Normal: Adding order items, firing to KDS, and bumping updates Floor to eating."""
        session = TableSession.objects.create(table=self.table, guest_name='Nabila')
        self.client.post(
            reverse('floor_kitchen:add_order_item', args=[session.pk]),
            {'menu_item_id': self.dish.pk, 'quantity': 2, 'special_note': 'No chili'},
        )
        self.client.post(reverse('floor_kitchen:send_to_kitchen', args=[session.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, DiningTable.STATUS_COOKING)

        ticket = KitchenTicket.objects.get(session=session)
        self.client.post(reverse('floor_kitchen:bump_ticket', args=[ticket.pk]))
        ticket.refresh_from_db()
        self.table.refresh_from_db()
        self.assertEqual(ticket.status, KitchenTicket.STATUS_BUMPED)
        self.assertEqual(self.table.status, DiningTable.STATUS_EATING)

    def test_kitchen_ticket_late_boundary_12_minutes(self):
        """Boundary: Ticket at 11m is on-time; ticket at 12m is marked late."""
        session = TableSession.objects.create(table=self.table, guest_name='Test')
        t_ok = KitchenTicket.objects.create(
            session=session,
            ticket_number='K-1',
            created_at=timezone.now() - timedelta(minutes=11),
        )
        t_late = KitchenTicket.objects.create(
            session=session,
            ticket_number='K-2',
            created_at=timezone.now() - timedelta(minutes=12),
        )
        self.assertFalse(t_ok.is_late)
        self.assertTrue(t_late.is_late)

    def test_cannot_remove_bumped_order_item(self):
        """Exceptional: Bumped items cannot be deleted from the session."""
        session = TableSession.objects.create(table=self.table, guest_name='Test')
        item = OrderItem.objects.create(
            session=session,
            menu_item=self.dish,
            quantity=1,
            unit_price=self.dish.selling_price,
            unit_cost=self.dish.prep_cost,
            status=OrderItem.STATUS_BUMPED,
        )
        self.client.post(reverse('floor_kitchen:remove_order_item', args=[item.pk]))
        self.assertTrue(OrderItem.objects.filter(pk=item.pk).exists())
