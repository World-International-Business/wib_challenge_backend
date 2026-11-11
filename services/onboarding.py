from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.jobs.models import JobApplication, OnboardingPlan
from services.agent_workflow import record_event
from services.recruitment_decisions import DecisionConflict, require_recruiter


def default_steps():
    return [
        {'id': key, 'title': title, 'status': 'pending'}
        for key, title in [
            ('administrative_documents', 'Collecter les pièces administratives'),
            ('access_provisioning', 'Préparer les accès'),
            ('equipment', 'Préparer le matériel'),
            ('welcome', 'Organiser l’accueil'),
            ('training', 'Préparer le parcours de formation'),
        ]
    ]


def default_objectives():
    return {'day30': [], 'day60': [], 'day90': []}


def initialize_onboarding(application):
    plan, created = OnboardingPlan.objects.get_or_create(
        application=application, defaults={'steps': default_steps(), 'objectives': default_objectives()},
    )
    if created:
        record_event(application, 'onboarding.plan_initialized')
    return plan


def onboarding_snapshot(application, plan=None):
    if plan is None:
        plan = OnboardingPlan.objects.filter(application=application).first()
    declarations = plan.administrative_documents if plan else []
    documents = [{'kind': 'signed_contract',
                  'status': 'received' if application.signed_contract_file and application.contract_status == 'signed' else 'missing',
                  'source': 'agent'}]
    by_kind = {item['kind']: item for item in declarations}
    for kind in ['identity_document', 'work_permit', 'bank_details', 'tax_registration', 'social_security']:
        documents.append({**by_kind.get(kind, {'kind': kind, 'status': 'missing'}),
                          'source': 'human' if kind in by_kind else 'pending'})
    return {
        'application_id': application.pk, 'eligible': application.status == 'accepted', 'initialized': plan is not None,
        'start_date': plan.start_date if plan else None,
        'steps': plan.steps if plan else default_steps(),
        'objectives': {**default_objectives(), **(plan.objectives if plan else {})},
        'administrative_documents': documents, 'version': plan.version if plan else 0,
        'updated_at': plan.updated_at if plan else None, 'updated_by': plan.updated_by_id if plan else None,
    }


@transaction.atomic
def update_onboarding(application_id, actor, data):
    application = JobApplication.objects.select_for_update().select_related('job_offer').get(pk=application_id)
    require_recruiter(application, actor)
    if application.status != 'accepted':
        raise ValidationError('Le plan ne peut être modifié que pour une candidature acceptée.')
    plan = initialize_onboarding(application)
    if data['expected_version'] != plan.version:
        raise DecisionConflict()
    changed = []
    for field in ['start_date', 'steps', 'objectives', 'administrative_documents']:
        if field not in data:
            continue
        value = data[field]
        if field == 'objectives':
            value = {**plan.objectives, **value}
        if getattr(plan, field) != value:
            setattr(plan, field, value)
            changed.append(field)
    if changed:
        plan.version += 1
        plan.updated_by = actor
        plan.save(update_fields=[*changed, 'version', 'updated_by', 'updated_at'])
        record_event(application, 'onboarding.updated', actor=actor,
                     data={'fields': changed, 'version': plan.version})
    return onboarding_snapshot(application, plan)
