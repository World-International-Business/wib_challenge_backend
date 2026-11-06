import os

from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Create admin user'

    def handle(self, *args, **options):
        from accounts.models import User

        email = os.getenv('ADMIN_EMAIL', '').strip()
        password = os.getenv('ADMIN_PASSWORD', '')
        first_name = os.getenv('ADMIN_FIRST_NAME', 'Admin').strip() or 'Admin'
        last_name = os.getenv('ADMIN_LAST_NAME', 'Admin').strip() or 'Admin'

        if not email or not password:
            self.stdout.write('ADMIN_EMAIL ou ADMIN_PASSWORD absent : aucun admin créé.')
            return

        user, created = User.objects.get_or_create(
            email=email,
            defaults={'first_name': first_name, 'last_name': last_name},
        )
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.email_verified = True
        user.set_password(password)
        if created:
            self.stdout.write(self.style.SUCCESS(f'Admin user created: {email}'))
        else:
            self.stdout.write(self.style.NOTICE(f'Admin user updated: {email}'))
        user.save()
