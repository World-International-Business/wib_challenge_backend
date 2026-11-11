from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.jobs.models import AgentEvent, JobApplication, ReviewNotification
from services.recruitment_decisions import require_recruiter


def record_event(application, action, *, actor=None, data=None, model_version='', human=False):
    return AgentEvent.objects.create(
        organization_id=application.job_offer.company_id, application=application,
        target_id=str(application.pk), action=action, actor='human' if actor or human else 'agent',
        input_data=data or {}, model_version=model_version, human_validator=actor,
    )


@transaction.atomic
def set_human_review(application_id, *, reason, actor=None, required=True):
    application = JobApplication.objects.select_for_update().select_related('job_offer').get(pk=application_id)
    if actor:
        require_recruiter(application, actor)
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError({'reason': 'Une justification est requise.'})
    if application.needs_human_review == required:
        return application
    application.needs_human_review = required
    application.review_reason = reason.strip() if required else ''
    application.decision_version += 1
    if required:
        application.review_generation += 1
    application.save(update_fields=['needs_human_review', 'review_reason', 'review_generation', 'decision_version', 'updated_at'])
    record_event(application, 'review.required' if required else 'review.resolved', actor=actor,
                 data={'generation': application.review_generation})
    if required:
        ReviewNotification.objects.get_or_create(application=application, generation=application.review_generation)
    return application


@transaction.atomic
def dispatch_review_notification(notification_id):
    notice = ReviewNotification.objects.select_for_update().select_related(
        'application__job_offer__company__account',
    ).get(pk=notification_id)
    application = notice.application
    if (notice.sent_count >= settings.REVIEW_NOTIFICATION_MAX_EMAILS or not application.needs_human_review
            or application.review_generation != notice.generation):
        return False
    if notice.next_attempt_at and notice.next_attempt_at > timezone.now():
        return False
    recipient = application.job_offer.company.account.email
    if not recipient:
        notice.error_code = 'missing_recipient'
        notice.next_attempt_at = timezone.now() + timedelta(hours=1)
        notice.save(update_fields=['error_code', 'next_attempt_at'])
        return False
    notice.attempts += 1
    try:
        sent = send_mail(
            'Recrutement : intervention requise',
            f'Une intervention est requise pour le dossier {application.pk}. '
            'Connectez-vous à votre espace recruteur pour consulter les détails.',
            settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False,
        )
        if not sent:
            raise RuntimeError('mail_not_accepted')
    except Exception:
        notice.error_code = 'delivery_failed'
        notice.next_attempt_at = timezone.now() + timedelta(minutes=min(60, 2 ** min(notice.attempts, 6)))
    else:
        notice.sent_at = timezone.now()
        notice.sent_count += 1
        notice.error_code = ''
        notice.next_attempt_at = timezone.now() + timedelta(hours=settings.REVIEW_NOTIFICATION_INTERVAL_HOURS)
        record_event(application, 'review.email_submitted', data={'generation': notice.generation, 'sequence': notice.sent_count})
    notice.save(update_fields=['attempts', 'sent_at', 'sent_count', 'error_code', 'next_attempt_at'])
    return not bool(notice.error_code)
