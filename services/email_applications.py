from typing import Iterable, Tuple, Optional, List

import email
import imaplib
from email.header import decode_header

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.encoding import force_str

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


def import_email_applications_from_imap() -> dict:
    """Importe les candidatures depuis la boîte email RH globale (IMAP).

    Cette fonction reprend la logique de la commande de management existante
    afin de pouvoir être appelée aussi bien en CLI que via une API REST.

    Retourne un résumé sous forme de dict:
    {
        "processed": <int>,  # nombre d'emails UNSEEN parcourus
        "created": <int>,    # nombre de JobApplication créées
        "skipped": <int>,    # emails ignorés (mauvais format, org/job introuvable, etc.)
        "errors": [str, ...] # erreurs rencontrées
    }
    """

    host = settings.IMAP_HOST
    username = settings.IMAP_USERNAME
    password = settings.IMAP_PASSWORD
    mailbox = getattr(settings, "IMAP_MAILBOX", "INBOX")
    port = getattr(settings, "IMAP_PORT", 993)

    if not host or not username or not password:
        return {
            "processed": 0,
            "created": 0,
            "skipped": 0,
            "errors": [
                "Configuration IMAP incomplète (IMAP_HOST/USERNAME/PASSWORD).",
            ],
        }

    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(username, password)
    imap.select(mailbox)

    status, messages = imap.search(None, "UNSEEN")
    if status != "OK":
        imap.logout()
        return {
            "processed": 0,
            "created": 0,
            "skipped": 0,
            "errors": [
                "Échec de la recherche des emails UNSEEN",
            ],
        }

    mail_ids = messages[0].split()
    processed = 0
    created = 0
    skipped = 0
    errors: List[str] = []

    for num in mail_ids:
        processed += 1
        try:
            status, data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                errors.append(f"Impossible de récupérer l'email {num!r}")
                skipped += 1
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            from_header = email.utils.parseaddr(msg.get("From", ""))
            from_name = from_header[0]
            from_email = from_header[1]

            # Décoder proprement le subject
            subject_parts = decode_header(msg.get("Subject", ""))
            subject_chunks: List[str] = []
            for part, enc in subject_parts:
                if isinstance(part, bytes):
                    subject_chunks.append(part.decode(enc or "utf-8", errors="ignore"))
                else:
                    subject_chunks.append(part)
            subject = "".join(subject_chunks)

            body = ""
            attachments: List[Attachment] = []

            for part in msg.walk():
                content_disposition = part.get("Content-Disposition", "")

                if part.get_content_maintype() == "text" and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body += payload.decode(charset, errors="ignore")
                    except Exception:
                        body += force_str(payload, errors="ignore")

                elif "attachment" in content_disposition:
                    filename = part.get_filename()
                    if not filename:
                        continue
                    payload = part.get_payload(decode=True) or b""
                    attachments.append((filename, payload))

            # Extraire ORG et JOB depuis le subject : [ORG-<id>][JOB-<id>]
            org_id = None
            job_id = None
            try:
                import re

                org_match = re.search(r"\\[ORG-(\\d+)\\]", subject)
                job_match = re.search(r"\\[JOB-(\\d+)\\]", subject)
                if org_match:
                    org_id = int(org_match.group(1))
                if job_match:
                    job_id = int(job_match.group(1))
            except Exception:
                org_id = None
                job_id = None

            if not org_id or not job_id:
                errors.append(
                    f"Impossible de trouver [ORG-x][JOB-y] dans le sujet: {subject!r}",
                )
                imap.store(num, '+FLAGS', r'\Seen')
                skipped += 1
                continue

            try:
                organization = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                errors.append(f"Organisation id={org_id} introuvable")
                imap.store(num, '+FLAGS', r'\Seen')
                skipped += 1
                continue

            try:
                job_offer = JobOffer.objects.get(id=job_id, company=organization)
            except JobOffer.DoesNotExist:
                errors.append(
                    f"Offre id={job_id} introuvable pour l'organisation {organization.id}",
                )
                imap.store(num, '+FLAGS', r'\Seen')
                skipped += 1
                continue

            application = create_application_from_email(
                organization=organization,
                job_offer=job_offer,
                from_name=from_name,
                from_email=from_email,
                subject=subject,
                body=body,
                attachments=attachments,
            )

            # Analyse CV en arrière-plan (optionnel)
            if getattr(settings, 'USE_CELERY_FOR_CV_ANALYSIS', False):
                try:
                    from apps.jobs.tasks import analyze_job_application_task

                    analyze_job_application_task.delay(application.id)
                except Exception as e:  # pragma: no cover - protection best effort
                    errors.append(f"Erreur lors de l'enqueue de l'analyse pour application id={application.id}: {e}")

            created += 1
            imap.store(num, '+FLAGS', r'\Seen')

        except Exception as e:
            errors.append(f"Erreur lors du traitement de l'email {num!r}: {e}")
            imap.store(num, '+FLAGS', r'\Seen')

    imap.close()
    imap.logout()

    return {
        "processed": processed,
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }
