from django.core.management.base import BaseCommand

from apps.jobs.tasks import dispatch_review_notifications


class Command(BaseCommand):
    help = 'Dispatch pending recruitment review notifications and due reminders'

    def handle(self, *args, **options):
        result = dispatch_review_notifications.run()
        self.stdout.write(f"Emails submitted to SMTP: {result['submitted']}")
