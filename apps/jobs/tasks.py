from celery import shared_task
from django.db import transaction

from apps.jobs.models import JobApplication
from services.cv_analyzer import analyze_job_application


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 5})
def analyze_job_application_task(self, application_id: int) -> dict:
    """Analyse une candidature en arrière-plan.

    Retourne un dict minimal pour logs/monitoring. Les résultats sont persistés en DB.
    """
    application = JobApplication.objects.select_related('job_offer').get(id=application_id)

    # analyse_job_application modifie et sauvegarde déjà l'application
    with transaction.atomic():
        analyze_job_application(application, application.job_offer, save=True)

    return {
        "application_id": application.id,
        "job_offer_id": application.job_offer_id,
        "ai_decision": application.ai_decision,
    }
