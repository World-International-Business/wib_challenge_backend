from io import StringIO
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase


class AdminBootstrapTests(TestCase):
    def run_command(self, **environment):
        output = StringIO()
        with patch.dict(os.environ, environment, clear=True):
            call_command('create_default_admin', stdout=output)
        return output.getvalue()

    def test_disabled_without_configuration(self):
        self.run_command()
        self.assertFalse(get_user_model().objects.filter(is_superuser=True).exists())

    def test_requires_both_values(self):
        with self.assertRaises(CommandError):
            self.run_command(BOOTSTRAP_ADMIN_EMAIL='admin@example.test')

    def test_rejects_weak_password(self):
        with self.assertRaises(CommandError):
            self.run_command(BOOTSTRAP_ADMIN_EMAIL='admin@example.test', BOOTSTRAP_ADMIN_PASSWORD='admin')
        self.assertFalse(get_user_model().objects.exists())

    def test_creates_admin_without_printing_password(self):
        password = 'Provisioning-7V!secure-29'
        output = self.run_command(BOOTSTRAP_ADMIN_EMAIL='admin@example.test', BOOTSTRAP_ADMIN_PASSWORD=password)
        user = get_user_model().objects.get(email='admin@example.test')
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertTrue(user.check_password(password))
        self.assertNotIn(password, output)

    def test_does_not_change_existing_credentials(self):
        user = get_user_model().objects.create_superuser(email='admin@example.test', password='existing-password')
        previous = user.password
        self.run_command(BOOTSTRAP_ADMIN_EMAIL=user.email, BOOTSTRAP_ADMIN_PASSWORD='Replacement-9V!secure')
        user.refresh_from_db()
        self.assertEqual(user.password, previous)

    def test_does_not_promote_existing_candidate(self):
        user = get_user_model().objects.create_user(email='candidate@example.test', password='existing-password')
        with self.assertRaises(CommandError):
            self.run_command(BOOTSTRAP_ADMIN_EMAIL=user.email, BOOTSTRAP_ADMIN_PASSWORD='Replacement-9V!secure')
        user.refresh_from_db()
        self.assertFalse(user.is_superuser or user.is_staff)
