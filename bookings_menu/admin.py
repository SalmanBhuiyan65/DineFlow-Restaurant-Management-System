"""Admin registration for Customers, Reservations, Waitlist, Tables, and Menu."""

from django.contrib import admin

from bookings_menu.models import (
    Customer,
    DiningTable,
    MenuCategory,
    MenuItem,
    Reservation,
    WaitlistEntry,
)

admin.site.register(Customer)
admin.site.register(MenuCategory)
admin.site.register(MenuItem)
admin.site.register(DiningTable)
admin.site.register(Reservation)
admin.site.register(WaitlistEntry)
