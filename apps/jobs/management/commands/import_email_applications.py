import imaplib
import email
from email.header import decode_header
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django.utils.encoding import force_str
from django.conf import settings

from apps.jobs.models import JobOffer
from apps.organizations.models import Organization
from services.email_applications import create_application_from_email


class Command(BaseCommand):
    help = "Importe les candidatures depuis la boîte email RH globale (IMAP)"

    def handle(self, *args, **options):
        host = settings.IMAP_HOST
        username = settings.IMAP_USERNAME
        password = settings.IMAP_PASSWORD
        mailbox = getattr(settings, "IMAP_MAILBOX", "INBOX")
        port = getattr(settings, "IMAP_PORT", 993)

        if not host or not username or not password:
            self.stderr.write(self.style.ERROR("Configuration IMAP incomplète (IMAP_HOST/USERNAME/PASSWORD)."))
            return

        self.stdout.write(self.style.NOTICE(f"Connexion IMAP à {host}:{port} en tant que {username}"))

        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(username, password)
        imap.select(mailbox)

        # Récupérer les emails non lus (UNSEEN)
        status, messages = imap.search(None, "UNSEEN")
        if status != "OK":
            self.stderr.write(self.style.ERROR("Échec de la recherche des emails UNSEEN"))
            imap.logout()
            return

        mail_ids = messages[0].split()
        self.stdout.write(self.style.NOTICE(f"{len(mail_ids)} email(s) non lus trouvés"))

        for num in mail_ids:
            try:
                status, data = imap.fetch(num, "(RFC822)")
                if status != "OK":
                    self.stderr.write(self.style.ERROR(f"Impossible de récupérer l'email {num!r}"))
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                from_header = email.utils.parseaddr(msg.get("From", ""))
                from_name = from_header[0]
                from_email = from_header[1]

                # Décoder le subject proprement
                subject_parts = decode_header(msg.get("Subject", ""))
                subject_chunks: List[str] = []
                for part, enc in subject_parts:
                    if isinstance(part, bytes):
                        subject_chunks.append(part.decode(enc or "utf-8", errors="ignore"))
                    else:
                        subject_chunks.append(part)
                subject = "".join(subject_chunks)

                body = ""
                attachments: List[Tuple[str, bytes]] = []

                for part in msg.walk():
                    content_disposition = part.get("Content-Disposition", "")
                    content_type = part.get_content_type()

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
                    # Recherche très simple, à adapter éventuellement
                    # Exemple: [ORG-3][JOB-15] Candidature ...
                    import re

                    org_match = re.search(r"\[ORG-(\d+)\]", subject)
                    job_match = re.search(r"\[JOB-(\d+)\]", subject)
                    if org_match:
                        org_id = int(org_match.group(1))
                    if job_match:
                        job_id = int(job_match.group(1))
                except Exception:
                    org_id = None
                    job_id = None

                if not org_id or not job_id:
                    self.stderr.write(self.style.WARNING(f"Impossible de trouver [ORG-x][JOB-y] dans le sujet: {subject!r}"))
                    # Marquer comme vu pour éviter de boucler indéfiniment, ou laisser UNSEEN si tu préfères les retraiter
                    imap.store(num, '+FLAGS', r'\Seen')
                    continue

                try:
                    organization = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    self.stderr.write(self.style.WARNING(f"Organisation id={org_id} introuvable"))
                    imap.store(num, '+FLAGS', r'\Seen')
                    continue

                try:
                    job_offer = JobOffer.objects.get(id=job_id, company=organization)
                except JobOffer.DoesNotExist:
                    self.stderr.write(self.style.WARNING(f"Offre id={job_id} introuvable pour l'organisation {organization.id}"))
                    imap.store(num, '+FLAGS', r'\Seen')
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
                    except Exception:
                        pass

                self.stdout.write(self.style.SUCCESS(
                    f"Candidature créée depuis l'email {from_email} pour l'offre {job_offer.id} (application id={application.id})"
                ))

                # Marquer l'email comme lu/traité
                imap.store(num, '+FLAGS', r'\Seen')

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Erreur lors du traitement de l'email {num!r}: {e}"))
                # On marque quand même comme vu pour éviter de boucler éternellement sur un email problématique
                imap.store(num, '+FLAGS', r'\Seen')

        imap.close()
        imap.logout()

        self.stdout.write(self.style.SUCCESS("Import des candidatures email terminé."))
