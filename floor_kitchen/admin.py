"""Admin registration for TableSessions, OrderItems, and KitchenTickets."""

from django.contrib import admin

from floor_kitchen.models import KitchenTicket, OrderItem, TableSession

admin.site.register(TableSession)
admin.site.register(OrderItem)
admin.site.register(KitchenTicket)
