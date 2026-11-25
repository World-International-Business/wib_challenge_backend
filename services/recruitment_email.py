import base64
import hashlib
import imaplib
import ipaddress
import re
import socket
import ssl
import unicodedata
import uuid
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from html.parser import HTMLParser

import fitz
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.jobs.models import AgentEvent, JobApplication, JobApplicationAnalysis, JobOffer
from apps.organizations.models import RecruitmentEmailInbox, RecruitmentEmailMessage
from services.channel_crypto import decrypt_secret, encrypt_secret

MAX_EMAIL_BYTES = 10 * 1024 * 1024
MAX_RESUME_BYTES = 5 * 1024 * 1024
BATCH_SIZE = 25


class MailboxError(Exception):
    pass


def public_address(host):
    try:
        addresses = socket.getaddrinfo(host, 993, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(item[4][0] for item in addresses))
        parsed = [ipaddress.ip_address(ip) for ip in ips]
        if not ips or any(not ip.is_global or ip.is_multicast or ip.is_reserved for ip in parsed):
            raise MailboxError('unsafe_host')
        return ips[0]
    except (OSError, ValueError) as exc:
        raise MailboxError('host_unreachable') from exc


class PublicIMAP(imaplib.IMAP4_SSL):
    def _create_socket(self, timeout):
        address = public_address(self.host)
        connection = socket.create_connection((address, self.port), timeout=timeout)
        try:
            return self.ssl_context.wrap_socket(connection, server_hostname=self.host)
        except Exception:
            connection.close()
            raise


def open_inbox(inbox):
    connection = None
    try:
        password = decrypt_secret(inbox.secret)
        if not password:
            raise MailboxError('credentials_unavailable')
        connection = PublicIMAP(inbox.host, 993, ssl_context=ssl.create_default_context(), timeout=15)
        connection.login(inbox.username, password)
        status, _ = connection.select('"' + inbox.folder.replace('\\', '\\\\').replace('"', '\\"') + '"', readonly=True)
        if status != 'OK':
            raise MailboxError('folder_unavailable')
        return connection
    except Exception as exc:
        if connection:
            close_inbox(connection)
        if isinstance(exc, MailboxError):
            raise
        code = 'authentication_failed' if isinstance(exc, imaplib.IMAP4.error) else 'connection_failed'
        raise MailboxError(code) from exc


def close_inbox(connection):
    try:
        connection.logout()
    except Exception:
        pass


def audit(inbox, action, *, actor=None, data=None):
    AgentEvent.objects.create(
        organization_id=inbox.organization_id, target_id=f'email-inbox:{inbox.pk}',
        action=action, actor='human' if actor else 'agent', human_validator=actor,
        input_data=data or {},
    )


def test_inbox(inbox):
    connection = open_inbox(inbox)
    close_inbox(connection)
    RecruitmentEmailInbox.objects.filter(pk=inbox.pk).update(verified_at=timezone.now(), error_code='')
    return {'status': 'connected', 'readOnly': True}


class ApplicationHTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self.hidden += 1
        if tag in ('br', 'p', 'div', 'li'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head') and self.hidden:
            self.hidden -= 1
        if tag in ('p', 'div', 'li'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def normalized_words(value):
    text = ''.join(char for char in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(char))
    return re.sub(r'[^\w+#]+', ' ', text).strip()


def has_application_message(body):
    for line in body.splitlines():
        line = line.strip()
        words = normalized_words(line)
        if line == '--' or words in ('cordialement', 'bien cordialement', 'best regards', 'regards', 'sincerely'):
            break
        if re.match(r'^(?:le .+ a ecrit|on .+ wrote)$', words):
            break
        if line.startswith('>') or words in ('bonjour', 'bonsoir', 'hello', 'hi', 'madame monsieur', 'merci', 'thanks'):
            continue
        content = re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+\.\w+', '', line)
        if any(char.isalpha() for char in content):
            return True
    return False


def parse_message(raw):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    name, sender = parseaddr(str(message.get('From', '')))
    try:
        validate_email(sender)
    except ValidationError as exc:
        raise MailboxError('invalid_sender') from exc
    body = message.get_body(preferencelist=('plain', 'html'))
    try:
        text = body.get_content()[:50000] if body else ''
        if body and body.get_content_type() == 'text/html':
            parser = ApplicationHTMLText()
            parser.feed(text)
            text = ''.join(parser.parts)
    except (LookupError, UnicodeError):
        text = ''
    return message, name[:255] or sender, sender, text


def choose_offer(inbox, subject):
    organizations = re.findall(r'\[ORG-(\d+)\]', subject, flags=re.IGNORECASE)
    offers = set(re.findall(r'\[JOB-(\d+)\]', subject, flags=re.IGNORECASE))
    if any(int(value) != inbox.organization_id for value in organizations) or len(offers) > 1:
        return None
    available = JobOffer.objects.filter(company_id=inbox.organization_id, status=JobOffer.Status.PUBLISHED).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    if offers:
        return available.filter(pk=int(next(iter(offers)))).first()
    subject_words = f' {normalized_words(subject)} '
    matches = [offer for offer in available if normalized_words(offer.title)
               and f' {normalized_words(offer.title)} ' in subject_words]
    if len(matches) == 1:
        return matches[0]
    if matches and len({normalized_words(offer.title) for offer in matches}) == 1:
        return next((offer for offer in matches if offer.pk == inbox.default_offer_id), None)
    return None


def pdf_attachment(message):
    candidates = [part for part in message.walk()
                  if part.get_filename() and str(part.get_filename()).lower().endswith('.pdf')]
    named = [part for part in candidates if re.search(r'cv|resume|curriculum', str(part.get_filename()), re.I)]
    selected = named if len(named) == 1 else candidates
    if len(selected) != 1:
        return None
    for part in selected:
        content = part.get_payload(decode=True) or b''
        if len(content) > MAX_RESUME_BYTES or not content.startswith(b'%PDF-'):
            continue
        try:
            with fitz.open(stream=content, filetype='pdf') as document:
                if (not document.is_encrypted and 0 < document.page_count <= 50 and not document.embfile_count()
                        and any(page.get_text().strip() or page.get_images() or page.get_drawings() for page in document)):
                    return content
        except Exception:
            continue
    return None


def application_parts(raw):
    message, name, sender, body = parse_message(raw)
    subject = normalized_words(str(message.get('Subject', '')))
    if not re.search(r'\b(?:candidatures?|postulation|postuler|job application|application for|applying for|apply for)\b', subject):
        raise MailboxError('candidacy_subject_required')
    if not has_application_message(body):
        raise MailboxError('application_message_required')
    content = pdf_attachment(message)
    if not content:
        raise MailboxError('missing_or_unsupported_resume')
    return message, name, sender, body, content


@transaction.atomic
def assign_message(message_id, offer, *, actor=None):
    receipt = RecruitmentEmailMessage.objects.select_for_update().select_related('inbox__organization').get(pk=message_id)
    inbox = receipt.inbox
    if offer.company_id != inbox.organization_id:
        raise MailboxError('offer_not_found')
    if actor and (not actor.is_authenticated or getattr(actor, 'organization', None) != inbox.organization):
        raise MailboxError('permission_denied')
    if receipt.status == 'imported':
        if receipt.application and receipt.application.job_offer_id != offer.pk:
            raise MailboxError('already_assigned')
        return receipt
    if receipt.status == 'ignored':
        raise MailboxError('automated_message')
    if offer.status != JobOffer.Status.PUBLISHED or (offer.expires_at and offer.expires_at <= timezone.now()):
        raise MailboxError('offer_not_open')
    if not receipt.raw_secret:
        raise MailboxError(receipt.error_code or 'message_unavailable')
    raw = base64.b64decode(decrypt_secret(receipt.raw_secret))
    message, name, sender, body, content = application_parts(raw)
    application = JobApplication.objects.create(
        job_offer=offer, applicant_name=name, applicant_email=sender, cover_letter=body,
        source=JobApplication.ApplicationSource.EMAIL,
    )
    receipt.resume_file.save(f'{uuid.uuid4().hex}.pdf', ContentFile(content), save=False)
    receipt.application = application
    receipt.status = 'imported'
    receipt.error_code = ''
    receipt.analysis_state = 'pending' if inbox.organization.auto_analyze_applications else 'manual'
    receipt.save(update_fields=['application', 'status', 'error_code', 'analysis_state', 'resume_file'])
    audit(inbox, 'email.application_imported', actor=actor, data={'message_id': receipt.pk, 'application_id': application.pk})
    return receipt


@transaction.atomic
def ingest_message(inbox, validity, uid, raw):
    fingerprint = hashlib.sha256(raw).hexdigest()
    existing = RecruitmentEmailMessage.objects.filter(inbox=inbox, fingerprint=fingerprint).first()
    if existing:
        return existing, False
    message = BytesParser(policy=policy.default).parsebytes(raw)
    _, sender = parseaddr(str(message.get('From', '')))
    receipt = RecruitmentEmailMessage.objects.create(
        inbox=inbox, fingerprint=fingerprint, uid_validity=validity, uid=uid,
        sender=sender[:254], subject=str(message.get('Subject', ''))[:255],
        raw_secret=encrypt_secret(base64.b64encode(raw).decode()),
    )
    platform_sender = parseaddr(settings.DEFAULT_FROM_EMAIL)[1].lower()
    automated = (str(message.get('Auto-Submitted', 'no')).lower().strip() != 'no'
                 or bool(message.get('List-Id')) or message.get_content_type() == 'multipart/report'
                 or (platform_sender and sender.lower() == platform_sender))
    if automated:
        receipt.status = 'ignored'
        receipt.error_code = 'automated_message'
        receipt.save(update_fields=['status', 'error_code'])
        return receipt, True
    try:
        application_parts(raw)
    except MailboxError as exc:
        receipt.status = 'incomplete'
        receipt.analysis_state = 'manual'
        receipt.error_code = str(exc)
        receipt.save(update_fields=['status', 'analysis_state', 'error_code'])
        audit(inbox, 'email.application_incomplete', data={'message_id': receipt.pk, 'error_code': receipt.error_code})
        return receipt, True
    offer = choose_offer(inbox, str(message.get('Subject', '')))
    if offer:
        try:
            receipt = assign_message(receipt.pk, offer)
        except MailboxError as exc:
            receipt.error_code = str(exc)
            receipt.save(update_fields=['error_code'])
    else:
        receipt.error_code = 'offer_assignment_required'
        receipt.save(update_fields=['error_code'])
    return receipt, True


def sync_inbox(inbox_id):
    now = timezone.now()
    token = str(uuid.uuid4())
    claimed = RecruitmentEmailInbox.objects.filter(pk=inbox_id, enabled=True, verified_at__isnull=False).filter(
        Q(locked_until__isnull=True) | Q(locked_until__lt=now),
    ).update(locked_until=now + timedelta(minutes=15), lease_token=token)
    if not claimed:
        return {'status': 'busy_or_disabled', 'processed': 0, 'created': 0}
    inbox = RecruitmentEmailInbox.objects.select_related('organization').get(pk=inbox_id)
    result = {'status': 'synced', 'processed': 0, 'created': 0, 'unassigned': 0}
    connection = None
    try:
        connection = open_inbox(inbox)
        _, values = connection.response('UIDVALIDITY')
        validity = values[0].decode() if values and values[0] else ''
        if not validity.isdigit():
            raise MailboxError('uid_validity_unavailable')
        cursor = inbox.last_uid if inbox.uid_validity == validity else 0
        status, values = connection.uid('search', None, f'UID {cursor + 1}:*')
        if status != 'OK':
            raise MailboxError('search_failed')
        uids = sorted(int(value) for value in (values[0] or b'').split() if int(value) > cursor)[:BATCH_SIZE]
        for uid in uids:
            if not RecruitmentEmailInbox.objects.filter(pk=inbox.pk, lease_token=token, enabled=True).exists():
                break
            status, sizes = connection.uid('fetch', str(uid), '(RFC822.SIZE)')
            match = re.search(rb'RFC822.SIZE (\d+)', b' '.join(item for item in sizes if isinstance(item, bytes))) if sizes else None
            if status != 'OK' or not match:
                raise MailboxError('fetch_failed')
            if int(match.group(1)) > MAX_EMAIL_BYTES:
                RecruitmentEmailMessage.objects.get_or_create(
                    inbox=inbox, uid_validity=validity, uid=uid,
                    defaults={'fingerprint': hashlib.sha256(f'oversize:{validity}:{uid}'.encode()).hexdigest(),
                              'status': 'error', 'error_code': 'message_too_large'},
                )
            else:
                status, data = connection.uid('fetch', str(uid), '(BODY.PEEK[])')
                raw = next((item[1] for item in data if isinstance(item, tuple)), None) if data else None
                if status != 'OK' or not isinstance(raw, bytes) or len(raw) > MAX_EMAIL_BYTES:
                    raise MailboxError('fetch_failed')
                receipt, created = ingest_message(inbox, validity, uid, raw)
                result['created'] += int(created and receipt.status == 'imported')
                result['unassigned'] += int(created and receipt.status == 'unassigned')
            result['processed'] += 1
            RecruitmentEmailInbox.objects.filter(pk=inbox.pk, lease_token=token).update(
                uid_validity=validity, last_uid=uid, locked_until=timezone.now() + timedelta(minutes=15))
        RecruitmentEmailInbox.objects.filter(pk=inbox.pk, lease_token=token).update(
            last_sync_at=timezone.now(), verified_at=timezone.now(), error_code='', failures=0,
            next_sync_at=timezone.now() + timedelta(seconds=60),
        )
        audit(inbox, 'email.sync_completed', data=result)
    except Exception as exc:
        code = str(exc) if isinstance(exc, MailboxError) else 'sync_failed'
        RecruitmentEmailInbox.objects.filter(pk=inbox.pk, lease_token=token).update(
            error_code=code, failures=inbox.failures + 1,
            next_sync_at=timezone.now() + timedelta(seconds=min(3600, 60 * 2 ** min(inbox.failures, 6))),
        )
        audit(inbox, 'email.sync_failed', data={'error_code': code})
        result.update(status='failed', errorCode=code)
    finally:
        if connection:
            close_inbox(connection)
        RecruitmentEmailInbox.objects.filter(pk=inbox.pk, lease_token=token).update(locked_until=None, lease_token='')
    return result


def analyze_pending_messages(inbox_id=None):
    now = timezone.now()
    eligible = RecruitmentEmailMessage.objects.filter(
        application__isnull=False, inbox__enabled=True, inbox__organization__auto_analyze_applications=True,
        analysis_state__in=['pending', 'processing'],
    ).filter(Q(analysis_next_attempt_at__isnull=True) | Q(analysis_next_attempt_at__lte=now)).filter(
        Q(analysis_locked_until__isnull=True) | Q(analysis_locked_until__lt=now))
    if inbox_id is not None:
        eligible = eligible.filter(inbox_id=inbox_id)
    completed = 0
    for message_id in list(eligible.order_by('pk').values_list('pk', flat=True)[:BATCH_SIZE]):
        with transaction.atomic():
            receipt = RecruitmentEmailMessage.objects.select_for_update().select_related('inbox__organization').get(pk=message_id)
            if receipt.analysis_locked_until and receipt.analysis_locked_until > timezone.now():
                continue
            if not receipt.application_id:
                receipt.analysis_state = 'cancelled'
                receipt.save(update_fields=['analysis_state'])
                continue
            if (receipt.analysis_state not in ('pending', 'processing') or not receipt.inbox.organization.auto_analyze_applications
                    or not receipt.inbox.enabled or (receipt.analysis_next_attempt_at and receipt.analysis_next_attempt_at > timezone.now())):
                continue
            if JobApplicationAnalysis.objects.filter(application_id=receipt.application_id, status='done').exists():
                receipt.analysis_state = 'done'
                receipt.analysis_locked_until = None
                receipt.error_code = ''
                receipt.save(update_fields=['analysis_state', 'analysis_locked_until', 'error_code'])
                completed += 1
                continue
            if receipt.analysis_attempts >= 5:
                receipt.analysis_state = 'failed'
                receipt.analysis_locked_until = None
                receipt.error_code = 'analysis_failed'
                receipt.save(update_fields=['analysis_state', 'analysis_locked_until', 'error_code'])
                from services.agent_workflow import set_human_review
                set_human_review(receipt.application_id, reason='Analyse email interrompue après plusieurs tentatives : intervention requise.')
                continue
            receipt.analysis_state = 'processing'
            receipt.analysis_attempts += 1
            receipt.analysis_locked_until = timezone.now() + timedelta(minutes=15)
            receipt.save(update_fields=['analysis_state', 'analysis_attempts', 'analysis_locked_until'])
        try:
            from services.cv_analyzer import analyze_job_application
            analyze_job_application(receipt.application, receipt.application.job_offer, save=True)
            if receipt.application.analysis.status == 'failed':
                raise MailboxError('analysis_failed')
        except Exception:
            final = receipt.analysis_attempts >= 5
            RecruitmentEmailMessage.objects.filter(pk=receipt.pk).update(
                analysis_state='failed' if final else 'pending', error_code='analysis_failed',
                analysis_next_attempt_at=timezone.now() + timedelta(minutes=2 ** receipt.analysis_attempts),
                analysis_locked_until=None,
            )
            if final:
                from services.agent_workflow import set_human_review
                set_human_review(receipt.application_id, reason='Analyse email en échec après plusieurs tentatives : intervention requise.')
        else:
            RecruitmentEmailMessage.objects.filter(pk=receipt.pk).update(
                analysis_state='done', error_code='', analysis_locked_until=None, analysis_next_attempt_at=None)
            completed += 1
    return {'analyzed': completed}
