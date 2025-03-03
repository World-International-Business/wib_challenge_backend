from datetime import timedelta

from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Setup default data for the app'

    def handle(self, *args, **options):
        # Create default challenge settings
        from challenges.models import Settings
        Settings.objects.create(default_challenge_duration=timedelta(hours=1))

        self.stdout.write(self.style.SUCCESS('Default settings created'))
