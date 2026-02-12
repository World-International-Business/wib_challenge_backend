from typing import Iterable, Tuple, Optional

from django.core.files.base import ContentFile
from django.utils import timezone

from apps.jobs.models import JobApplication, JobOffer
from apps.organizations.models import Organization


Attachment = Tuple[str, bytes]


def create_application_from_email(
    *,
    organization: Organization,
    job_offer: Optional[JobOffer],
    from_name: Optional[str],
    from_email: str,
    subject: str,
    body: str,
    attachments: Iterable[Attachment],
) -> JobApplication:
    """Crée une JobApplication à partir des données d'un email.

    - organisation et job_offer permettent de rattacher la candidature
    - from_name / from_email peuplent applicant_name / applicant_email
    - body devient une lettre de motivation de base
    - la première pièce jointe ressemblant à un CV est enregistrée dans resume
    """

    applicant_name = (from_name or '').strip() or from_email

    application = JobApplication.objects.create(
        job_offer=job_offer,
        applicant_name=applicant_name,
        applicant_email=from_email,
        cover_letter=body or "",
        source=JobApplication.ApplicationSource.EMAIL,
        status=JobApplication.ApplicationStatus.PENDING,
        submitted_at=timezone.now(),
    )

    # Attacher le premier fichier qui ressemble à un CV
    for filename, content in attachments:
        lower = filename.lower()
        if lower.endswith((".pdf", ".doc", ".docx")):
            application.resume.save(
                filename,
                ContentFile(content),
                save=True,
            )
            break

    return application
