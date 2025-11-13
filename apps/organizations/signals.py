from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.organizations.models import Notification
from apps.jobs.models import JobApplication
from apps.evaluations.models import Submission


@receiver(post_save, sender=JobApplication)
def create_notification_on_new_application(sender, instance: JobApplication, created, **kwargs):
    if not created:
        return
    try:
        org = instance.job_offer.company
    except Exception:
        return

    Notification.objects.create(
        organization=org,
        type=Notification.Types.NEW_APPLICATION,
        title="Nouvelle candidature",
        message=f"{instance.applicant_name} a postulé pour {instance.job_offer.title}",
        related_application=instance,
    )


@receiver(post_save, sender=Submission)
def create_notification_on_test_completed(sender, instance: Submission, created, **kwargs):
    # Une soumission créée = test terminé
    try:
        evaluation = instance.attempt.evaluation
        publisher = evaluation.publisher
        if not hasattr(publisher, 'organization') or publisher.organization is None:
            return
        org = publisher.organization
    except Exception:
        return

    related_app = JobApplication.objects.filter(
        assigned_evaluation=evaluation,
        job_offer__company=org
    ).first()

    Notification.objects.create(
        organization=org,
        type=Notification.Types.TEST_COMPLETED,
        title="Test terminé",
        message=f"Une évaluation a été complétée: {evaluation.title}",
        related_evaluation=evaluation,
        related_application=related_app,
    )
