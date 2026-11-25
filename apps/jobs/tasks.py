from celery import shared_task
from django.conf import settings
from django.db import transaction

from apps.jobs.models import JobApplication, ReviewNotification
from django.db.models import F, Q
from django.utils import timezone
from services.cv_analyzer import analyze_job_application


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 5})
def analyze_job_application_task(self, application_id: int, automatic: bool = False) -> dict:
    """Analyse une candidature en arrière-plan.

    Retourne un dict minimal pour logs/monitoring. Les résultats sont persistés en DB.
    """
    application = JobApplication.objects.select_related('job_offer__company').get(id=application_id)
    if automatic and not application.job_offer.company.auto_analyze_applications:
        return {'application_id': application.id, 'skipped': 'automatic_analysis_disabled'}

    # analyse_job_application modifie et sauvegarde déjà l'application
    try:
        with transaction.atomic():
            analyze_job_application(application, application.job_offer, save=True)
    except Exception:
        if self.request.retries >= 5:
            from services.agent_workflow import record_event, set_human_review
            record_event(application, 'analysis.failed', data={'reason': 'processing_failed'})
            set_human_review(application.pk, reason='Analyse en échec après plusieurs tentatives : intervention requise.')
        raise

    return {
        "application_id": application.id,
        "job_offer_id": application.job_offer_id,
        "ai_decision": application.ai_decision,
    }


@shared_task
def dispatch_review_notifications():
    from services.agent_workflow import dispatch_review_notification

    ids = ReviewNotification.objects.filter(
        sent_count__lt=settings.REVIEW_NOTIFICATION_MAX_EMAILS, application__needs_human_review=True,
        application__job_offer__company__notify_blocking_cases=True,
        generation=F('application__review_generation'),
    ).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now()),
    ).order_by('pk').values_list('pk', flat=True)[:100]
    sent = sum(dispatch_review_notification(pk) for pk in list(ids))
    return {'submitted': sent}


@shared_task(soft_time_limit=600, time_limit=660)
def sync_recruitment_inbox(inbox_id):
    from services.recruitment_email import sync_inbox
    return sync_inbox(inbox_id)


@shared_task
def sync_recruitment_inboxes():
    from apps.organizations.models import RecruitmentEmailInbox
    now = timezone.now()
    ids = RecruitmentEmailInbox.objects.filter(enabled=True, verified_at__isnull=False).filter(
        Q(next_sync_at__isnull=True) | Q(next_sync_at__lte=now),
    ).filter(Q(locked_until__isnull=True) | Q(locked_until__lt=now)).order_by('next_sync_at', 'pk').values_list('pk', flat=True)[:100]
    queued = 0
    for inbox_id in ids:
        sync_recruitment_inbox.apply_async(args=[inbox_id], expires=300)
        queued += 1
    return {'queued': queued}


@shared_task(soft_time_limit=600, time_limit=660)
def analyze_recruitment_emails():
    from services.recruitment_email import analyze_pending_messages
    return analyze_pending_messages()
