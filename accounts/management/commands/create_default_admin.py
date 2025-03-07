from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Create admin user'

    def handle(self, *args, **options):
        from accounts.models import User

        user, created = User.objects.get_or_create(email='admin@wibchallenge.com', first_name='Admin',
                                                   last_name='Admin')
        if created:
            user.is_staff = True
            user.is_superuser = True
            user.set_password('admin')
            user.save()
            self.stdout.write(self.style.SUCCESS('Admin user created successfully'))
        else:
            self.stdout.write(self.style.NOTICE('Admin user already exists'))
