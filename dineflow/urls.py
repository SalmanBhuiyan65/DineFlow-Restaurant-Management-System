"""Root URL configuration for DineFlow Restaurant Management System."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('floor_kitchen.urls')),
    path('', include('bookings_menu.urls')),
    path('', include('billing_analytics.urls')),
]
