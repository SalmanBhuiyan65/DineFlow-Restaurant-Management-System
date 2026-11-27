"""Admin registration for staff profiles."""

from django.contrib import admin

from accounts.models import StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    """Admin view for StaffProfile."""

    list_display = ('display_name', 'user', 'role')
    list_filter = ('role',)
