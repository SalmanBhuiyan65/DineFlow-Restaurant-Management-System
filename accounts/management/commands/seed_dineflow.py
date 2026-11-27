"""Seed realistic DineFlow dinner-service data for instant demonstration."""

from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import StaffProfile
from billing_analytics.models import (
    Bill,
    HistoricalDailySummary,
    MonthlyFinancialSummary,
    Payment,
)
from bookings_menu.models import (
    Customer,
    DiningTable,
    MenuCategory,
    MenuItem,
    Reservation,
    WaitlistEntry,
)
from floor_kitchen.models import KitchenTicket, OrderItem, TableSession


class Command(BaseCommand):
    """Populate DineFlow with staff, customers, menu images, and P&L data."""

    help = 'Seed DineFlow with realistic dinner-service demo data.'

    def handle(self, *args, **options):
        """Execute idempotent database seeding."""
        now = timezone.now()

        # 1. Staff accounts
        staff_specs = [
            ('salman', 'Salman', StaffProfile.ROLE_WAITER),
            ('orin', 'Orin', StaffProfile.ROLE_HOST),
            ('hasibul', 'Hasibul', StaffProfile.ROLE_MANAGER),
            ('chef', 'Chef Tariq', StaffProfile.ROLE_KITCHEN),
        ]
        users = {}
        for username, display_name, role in staff_specs:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password('dineflow123')
                user.save()
            StaffProfile.objects.update_or_create(
                user=user,
                defaults={'role': role, 'display_name': display_name},
            )
            users[username] = user

        # 2. Customers
        cust_specs = [
            ('Nabila Rahman', '01711-000111', 'nabila@example.com'),
            ('Rafiqul Islam', '01812-333444', 'rafiq@example.com'),
            ('Farhana Kabir', '01913-555666', 'farhana@example.com'),
        ]
        customers = {}
        for name, phone, email in cust_specs:
            cust, _ = Customer.objects.get_or_create(
                phone=phone, defaults={'name': name, 'email': email}
            )
            customers[name] = cust

        # 3. Dining Tables
        table_specs = [
            ('T1', 2, 'Window', DiningTable.STATUS_COOKING),
            ('T2', 2, 'Window', DiningTable.STATUS_EMPTY),
            ('T3', 4, 'Main Hall', DiningTable.STATUS_ORDERING),
            ('T4', 4, 'Main Hall', DiningTable.STATUS_EMPTY),
            ('T5', 4, 'Main Hall', DiningTable.STATUS_EATING),
            ('T6', 6, 'Patio', DiningTable.STATUS_RESERVED),
            ('T7', 6, 'Patio', DiningTable.STATUS_EMPTY),
            ('T8', 8, 'Main Hall', DiningTable.STATUS_EMPTY),
        ]
        tables = {}
        for code, cap, zone, status in table_specs:
            table, _ = DiningTable.objects.get_or_create(
                code=code,
                defaults={'capacity': cap, 'zone': zone, 'status': status},
            )
            tables[code] = table

        # 4. Menu Categories & Items with local food images
        cat_names = ['Starters', 'Mains', 'Grills', 'Beverages', 'Desserts']
        cats = {}
        for idx, name in enumerate(cat_names):
            cat, _ = MenuCategory.objects.get_or_create(
                name=name, defaults={'display_order': idx}
            )
            cats[name] = cat

        menu_specs = [
            ('Starters', 'Crispy Calamari', 'Lightly spiced squid',
             '180.00', '420.00', 'images/menu/calamari.jpg'),
            ('Starters', 'Beef Tacos Platter', 'Shredded beef & salsa',
             '210.00', '490.00', 'images/menu/beef_tacos.jpg'),
            ('Mains', 'Butter Chicken & Naan', 'Creamy tomato gravy',
             '240.00', '580.00', 'images/menu/butter_chicken.jpg'),
            ('Mains', 'Pesto Alfredo Pasta', 'Fettuccine & basil pesto',
             '190.00', '460.00', 'images/menu/pesto_pasta.jpg'),
            ('Mains', 'Mushroom Risotto', 'Creamy wild mushroom',
             '220.00', '540.00', 'images/menu/mushroom_risotto.jpg'),
            ('Grills', 'Smoked Ribeye Steak', '300g char-grilled',
             '650.00', '1450.00', 'images/menu/ribeye_steak.jpg'),
            ('Grills', 'Pan-Seared Salmon', 'Crispy skin & herb butter',
             '480.00', '1150.00', 'images/menu/salmon.jpg'),
            ('Beverages', 'Iced Caramel Latte', 'Double espresso & caramel',
             '80.00', '260.00', 'images/menu/caramel_latte.jpg'),
            ('Beverages', 'Mango Smoothie', 'Fresh blended mango',
             '70.00', '220.00', 'images/menu/mango_smoothie.jpg'),
            ('Desserts', 'Molten Lava Cake', 'Warm dark chocolate cake',
             '120.00', '340.00', 'images/menu/lava_cake.jpg'),
        ]
        items = {}
        for cat_name, name, desc, cost, price, img in menu_specs:
            item, _ = MenuItem.objects.update_or_create(
                name=name,
                defaults={
                    'category': cats[cat_name],
                    'description': desc,
                    'prep_cost': Decimal(cost),
                    'selling_price': Decimal(price),
                    'image_path': img,
                    'is_available': True,
                },
            )
            items[name] = item

        # 5. Live Sessions, Kitchen Tickets & Partial Due Demo
        if not TableSession.objects.exists():
            s1 = TableSession.objects.create(
                table=tables['T1'],
                customer=customers['Rafiqul Islam'],
                guest_name='Rafiqul Islam',
                guest_count=2,
                waiter=users['salman'],
                started_at=now - timedelta(minutes=18),
            )
            OrderItem.objects.create(
                session=s1,
                menu_item=items['Smoked Ribeye Steak'],
                quantity=2,
                unit_price=items['Smoked Ribeye Steak'].selling_price,
                unit_cost=items['Smoked Ribeye Steak'].prep_cost,
                special_note='Medium rare',
                status=OrderItem.STATUS_SENT,
                created_at=now - timedelta(minutes=14),
            )
            KitchenTicket.objects.create(
                session=s1,
                ticket_number='K-101',
                status=KitchenTicket.STATUS_QUEUED,
                notes='2x Smoked Ribeye Steak (Medium rare)',
                created_at=now - timedelta(minutes=14),
            )

            s3 = TableSession.objects.create(
                table=tables['T3'],
                customer=customers['Farhana Kabir'],
                guest_name='Farhana Kabir',
                guest_count=4,
                waiter=users['salman'],
                started_at=now - timedelta(minutes=6),
            )
            OrderItem.objects.create(
                session=s3,
                menu_item=items['Butter Chicken & Naan'],
                quantity=2,
                unit_price=items['Butter Chicken & Naan'].selling_price,
                unit_cost=items['Butter Chicken & Naan'].prep_cost,
                status=OrderItem.STATUS_DRAFT,
            )
            OrderItem.objects.create(
                session=s3,
                menu_item=items['Mango Smoothie'],
                quantity=4,
                unit_price=items['Mango Smoothie'].selling_price,
                unit_cost=items['Mango Smoothie'].prep_cost,
                status=OrderItem.STATUS_DRAFT,
            )

            s5 = TableSession.objects.create(
                table=tables['T5'],
                guest_name='Zahin',
                guest_count=3,
                waiter=users['salman'],
                started_at=now - timedelta(minutes=32),
            )
            OrderItem.objects.create(
                session=s5,
                menu_item=items['Pan-Seared Salmon'],
                quantity=2,
                unit_price=items['Pan-Seared Salmon'].selling_price,
                unit_cost=items['Pan-Seared Salmon'].prep_cost,
                status=OrderItem.STATUS_BUMPED,
            )
            KitchenTicket.objects.create(
                session=s5,
                ticket_number='K-100',
                status=KitchenTicket.STATUS_BUMPED,
                created_at=now - timedelta(minutes=28),
                bumped_at=now - timedelta(minutes=17),
            )

            # Completed & paid session for Nabila
            s_paid = TableSession.objects.create(
                table=tables['T4'],
                customer=customers['Nabila Rahman'],
                guest_name='Nabila Rahman',
                guest_count=4,
                waiter=users['salman'],
                started_at=now - timedelta(hours=2),
                ended_at=now - timedelta(hours=1),
                is_active=False,
            )
            for dish_name, qty in [
                ('Crispy Calamari', 2),
                ('Pesto Alfredo Pasta', 3),
                ('Molten Lava Cake', 2),
            ]:
                dish = items[dish_name]
                OrderItem.objects.create(
                    session=s_paid,
                    menu_item=dish,
                    quantity=qty,
                    unit_price=dish.selling_price,
                    unit_cost=dish.prep_cost,
                    status=OrderItem.STATUS_BUMPED,
                )
            bill = Bill.objects.create(session=s_paid, customer=customers['Nabila Rahman'])
            bill.recalculate()
            bill.paid_amount = bill.total
            bill.due_amount = Decimal('0.00')
            bill.status = Bill.STATUS_PAID
            bill.paid_at = now - timedelta(hours=1)
            bill.save()
            Payment.objects.create(
                bill=bill,
                method=Payment.METHOD_BKASH,
                amount=bill.total,
                recorded_by=users['hasibul'],
                recorded_at=now - timedelta(hours=1),
            )

            # Partial / Due bill example for Rafiqul Islam
            s_due = TableSession.objects.create(
                table=tables['T7'],
                customer=customers['Rafiqul Islam'],
                guest_name='Rafiqul Islam',
                guest_count=3,
                waiter=users['salman'],
                started_at=now - timedelta(days=2),
                ended_at=now - timedelta(days=2) + timedelta(hours=1),
                is_active=False,
            )
            for dish_name, qty in [('Beef Tacos Platter', 2), ('Iced Caramel Latte', 2)]:
                dish = items[dish_name]
                OrderItem.objects.create(
                    session=s_due,
                    menu_item=dish,
                    quantity=qty,
                    unit_price=dish.selling_price,
                    unit_cost=dish.prep_cost,
                    status=OrderItem.STATUS_BUMPED,
                )
            due_bill = Bill.objects.create(session=s_due, customer=customers['Rafiqul Islam'])
            due_bill.recalculate()
            due_bill.paid_amount = Decimal('1000.00')
            due_bill.due_amount = due_bill.total - Decimal('1000.00')
            due_bill.status = Bill.STATUS_PARTIAL
            due_bill.save()
            Payment.objects.create(
                bill=due_bill,
                method=Payment.METHOD_CASH,
                amount=Decimal('1000.00'),
                recorded_by=users['hasibul'],
                recorded_at=now - timedelta(days=2),
            )

        # 6. Reservations & Walk-in Waitlist
        if not Reservation.objects.exists():
            Reservation.objects.create(
                guest_name='Nabila',
                phone='01711-000111',
                party_size=2,
                table=tables['T2'],
                reserved_for=now + timedelta(minutes=20),
                status=Reservation.STATUS_BOOKED,
                notes='Window table requested',
            )
            Reservation.objects.create(
                guest_name='Mahmudul',
                phone='01812-222333',
                party_size=6,
                table=tables['T6'],
                reserved_for=now + timedelta(minutes=45),
                status=Reservation.STATUS_BOOKED,
                notes='Family dinner',
            )

        if not WaitlistEntry.objects.exists():
            WaitlistEntry.objects.create(
                guest_name='Sadia & Friends',
                phone='01911-444555',
                party_size=4,
                estimated_wait_minutes=15,
            )

        # 7. Previous Equivalent Day Summary
        yesterday = timezone.localdate() - timedelta(days=1)
        HistoricalDailySummary.objects.get_or_create(
            service_date=yesterday,
            defaults={
                'total_sales': Decimal('18450.00'),
                'guests_served': 34,
                'table_turns': 11,
                'hourly_breakdown_json': {'18:00': 4200, '19:00': 6800, '20:00': 7450},
                'payment_breakdown_json': {'cash': 6200, 'card': 7800, 'bkash': 4450},
            },
        )

        # 8. 12-Month Yearly Profit & Loss Summary
        pnl_specs = [
            (1, 'Jan', '310000', '124000', '145000'),
            (2, 'Feb', '275000', '112000', '172000'),
            (3, 'Mar', '345000', '138000', '150000'),
            (4, 'Apr', '390000', '156000', '155000'),
            (5, 'May', '420000', '165000', '160000'),
            (6, 'Jun', '295000', '125000', '180000'),
            (7, 'Jul', '365000', '142000', '155000'),
            (8, 'Aug', '410000', '160000', '162000'),
            (9, 'Sep', '445000', '175000', '165000'),
            (10, 'Oct', '480000', '188000', '170000'),
            (11, 'Nov', '515000', '200000', '175000'),
            (12, 'Dec', '560000', '215000', '185000'),
        ]
        for month, label, rev, cogs, opex in pnl_specs:
            MonthlyFinancialSummary.objects.get_or_create(
                year=2026,
                month=month,
                defaults={
                    'label': label,
                    'revenue': Decimal(rev),
                    'cogs': Decimal(cogs),
                    'operating_expenses': Decimal(opex),
                },
            )

        self.stdout.write(self.style.SUCCESS('DineFlow seed data loaded successfully.'))
