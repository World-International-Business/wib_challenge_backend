from django.db import migrations


def backfill_decisions(apps, schema_editor):
    decisions = apps.get_model('jobs', 'RecruitmentDecisionEvent')
    events = apps.get_model('jobs', 'AgentEvent')
    alias = schema_editor.connection.alias
    for decision in decisions.objects.using(alias).select_related('application__job_offer').iterator():
        event, _ = events.objects.using(alias).get_or_create(
            organization_id=decision.application.job_offer.company_id,
            application_id=decision.application_id,
            action='application.status_changed', actor='human',
            target_id=str(decision.application_id), human_validator_id=decision.actor_id,
            input_data={'from_status': decision.from_status, 'to_status': decision.to_status,
                        'legacy_decision_id': decision.pk, 'policy_version': decision.policy_version},
        )
        events.objects.using(alias).filter(pk=event.pk).update(timestamp=decision.created_at)


class Migration(migrations.Migration):
    dependencies = [('jobs', '0016_jobapplication_needs_human_review_and_more')]
    operations = [migrations.RunPython(backfill_decisions, migrations.RunPython.noop)]
