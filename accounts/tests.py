"""Unit tests for staff authentication and demo role switching."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import StaffProfile


class AccountsTests(TestCase):
    """Verify staff login and 1-click demo role switcher."""

    def setUp(self):
        self.user = User.objects.create_user(username='salman', password='pw')
        StaffProfile.objects.create(
            user=self.user,
            role=StaffProfile.ROLE_WAITER,
            display_name='Salman',
        )

    def test_switch_role_logs_in_demo_user(self):
        """Normal: Demo role switcher logs in the matching StaffProfile user."""
        resp = self.client.post(
            reverse('accounts:switch_role', args=[StaffProfile.ROLE_WAITER])
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
