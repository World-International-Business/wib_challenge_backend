from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from apps.jobs.models import JobApplication
from apps.organizations.models import Notification


class Command(BaseCommand):
    help = "Send notifications to organizations 30 minutes before scheduled interviews"

    def handle(self, *args, **options):
        now = timezone.now()
        target_start = now + timedelta(minutes=30)
        # Petite fenêtre pour éviter le timing strict (ex: job toutes les minutes)
        window_end = target_start + timedelta(minutes=2)

        interviews = JobApplication.objects.filter(
            interview_date__gte=target_start,
            interview_date__lte=window_end,
            job_offer__company__isnull=False,
        ).select_related('job_offer__company')

        created = 0
        for app in interviews:
            org = app.job_offer.company
            # Éviter les doublons: existe-t-il déjà un rappel récent pour cette application ?
            exists = Notification.objects.filter(
                organization=org,
                type=Notification.Types.INTERVIEW_REMINDER,
                related_application=app,
                created_at__gte=now - timedelta(hours=1),
            ).exists()
            if exists:
                continue

            Notification.objects.create(
                organization=org,
                type=Notification.Types.INTERVIEW_REMINDER,
                title="Rappel d'entretien",
                message=(
                    f"Entretien dans 30 minutes pour '{app.job_offer.title}' avec "
                    f"{app.applicant_name}."
                ),
                related_application=app,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Interview reminders created: {created}"))
