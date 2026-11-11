from django.db import transaction
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.jobs.models import JobApplication, RecruitmentDecisionEvent


POLICY_VERSION = 'human-decisions-v1'
TRANSITIONS = {
    'pending': ['shortlisted', 'rejected'],
    'shortlisted': ['pending', 'accepted', 'rejected'],
    'accepted': ['pending'],
    'rejected': ['pending'],
}


class DecisionConflict(APIException):
    status_code = 409
    default_detail = 'Le dossier a changé. Rechargez-le avant de prendre une décision.'
    default_code = 'stale_decision'


def require_recruiter(application, actor):
    organization = getattr(actor, 'organization', None)
    if not actor.is_authenticated or not (
        actor.is_staff or (organization and application.job_offer.company_id == organization.pk)
    ):
        raise PermissionDenied('Seul un recruteur autorisé peut effectuer cette action.')


def decision_options(application, actor):
    require_recruiter(application, actor)
    return {
        'status': application.status,
        'version': application.decision_version,
        'policy_version': POLICY_VERSION,
        'allowed_statuses': TRANSITIONS.get(application.status, []),
        'reason_required_for': ['accepted', 'rejected', 'pending'],
    }


@transaction.atomic
def change_application_status(*, application_id, actor, target, recruitment_details=None, reason='', expected_version=None):
    application = JobApplication.objects.select_for_update().select_related('job_offer').get(pk=application_id)
    require_recruiter(application, actor)
    if target not in JobApplication.ApplicationStatus.values:
        raise ValidationError({'status': 'Statut de candidature invalide.'})
    if expected_version is not None:
        if type(expected_version) is not int or expected_version < 0:
            raise ValidationError({'expected_version': 'Une version entière positive ou nulle est attendue.'})
        if expected_version != application.decision_version:
            raise DecisionConflict()
    if not isinstance(reason, str):
        raise ValidationError({'reason': 'Une justification textuelle est attendue.'})
    if recruitment_details is not None and not isinstance(recruitment_details, str):
        raise ValidationError({'recruitment_details': 'Un texte est attendu.'})
    previous = application.status
    if previous != target:
        if target not in TRANSITIONS.get(previous, []):
            raise ValidationError({'status': 'Transition interdite depuis le statut actuel.'})
        if target in ('accepted', 'rejected', 'pending') and not reason.strip():
            raise ValidationError({'reason': 'Cette décision nécessite une justification humaine.'})
    application.status = target
    fields = ['status', 'updated_at', 'decision_version']
    if recruitment_details:
        application.recruitment_details = recruitment_details
        fields.append('recruitment_details')
    if previous != target or recruitment_details:
        application.decision_version += 1
    application.save(update_fields=fields)
    if previous != target:
        RecruitmentDecisionEvent.objects.create(
            application=application, actor=actor, from_status=previous,
            to_status=target, reason=reason.strip(), policy_version=POLICY_VERSION,
        )
        from services.agent_workflow import record_event
        record_event(application, 'application.status_changed', actor=actor,
                     data={'from_status': previous, 'to_status': target, 'policy_version': POLICY_VERSION})
        if application.needs_human_review:
            application.needs_human_review = False
            application.review_reason = ''
            application.save(update_fields=['needs_human_review', 'review_reason'])
            record_event(application, 'review.resolved', actor=actor)
    return application, previous
