"""Models for staff authentication and role profiles in DineFlow."""

from django.contrib.auth.models import User
from django.db import models


class StaffProfile(models.Model):
    """Stores the operational restaurant role for a staff user.

    Attributes:
        user: Linked Django auth User instance.
        role: Staff role (host, waiter, kitchen, or manager).
        display_name: Human-readable staff name shown in the dashboard.
    """

    ROLE_HOST = 'host'
    ROLE_WAITER = 'waiter'
    ROLE_KITCHEN = 'kitchen'
    ROLE_MANAGER = 'manager'

    ROLE_CHOICES = [
        (ROLE_HOST, 'Host / Reception'),
        (ROLE_WAITER, 'Waitstaff'),
        (ROLE_KITCHEN, 'Kitchen Chef'),
        (ROLE_MANAGER, 'Floor Manager / Cashier'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='staff_profile',
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_WAITER,
    )
    display_name = models.CharField(max_length=80)

    def __str__(self):
        """Return display name and role label."""
        return f'{self.display_name} ({self.get_role_display()})'
