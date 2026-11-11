import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction


class Command(BaseCommand):
    help = 'Provision an administrator only when explicitly configured'

    requires_migrations_checks = True

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.accounts.models import User

        email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', '').strip()
        password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', '')
        if not email and not password:
            self.stdout.write('Administrator bootstrap disabled.')
            return
        if not email or not password:
            raise CommandError('Both BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD are required.')
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError('Invalid bootstrap administrator email.') from exc
        email = User.objects.normalize_email(email)
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if not existing.is_superuser or not existing.is_staff or not existing.is_active:
                raise CommandError('The configured account already exists and is not an active administrator.')
            self.stdout.write('Administrator already exists; credentials unchanged.')
            return
        user = User(email=email, first_name='Admin', role=User.Roles.ADMIN)
        try:
            validate_password(password, user=user)
        except ValidationError as exc:
            raise CommandError('Bootstrap password does not satisfy password policy.') from exc
        User.objects.create_superuser(email=email, password=password, first_name='Admin')
        self.stdout.write(self.style.SUCCESS('Administrator created successfully.'))
