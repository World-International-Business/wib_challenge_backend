from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Create admin user'

    def handle(self, *args, **options):
        from accounts.models import User

        User.objects.create_superuser(email='admin@wibchallenge.com', password='admin', first_name='Admin',
                                      last_name='Admin')
        self.stdout.write(self.style.SUCCESS('Admin user created successfully'))
