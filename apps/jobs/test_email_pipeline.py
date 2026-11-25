from datetime import timedelta
from email.message import EmailMessage
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import fitz
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.jobs.models import AgentEvent, JobApplication, JobCategory, JobOffer, ReviewNotification
from apps.organizations.models import Notification, Organization, RecruitmentEmailInbox, RecruitmentEmailMessage
from services.channel_crypto import decrypt_secret, encrypt_secret
from services.cv_analyzer import Response as AnalysisResponse
from services.recruitment_email import (
    MailboxError, PublicIMAP, analyze_pending_messages, assign_message, choose_offer,
    ingest_message, open_inbox, public_address, sync_inbox,
)


class FakeIMAP:
    def __init__(self, messages, validity=b'42'):
        self.messages = messages
        self.validity = validity
        self.calls = []
        self.logged_out = False

    def response(self, name):
        return name, [self.validity]

    def uid(self, command, *args):
        self.calls.append((command, args))
        if command == 'search':
            return 'OK', [b' '.join(str(uid).encode() for uid in self.messages)]
        uid = int(args[0])
        raw = self.messages[uid]
        if args[1] == '(RFC822.SIZE)':
            return 'OK', [f'{uid} (RFC822.SIZE {len(raw)})'.encode()]
        return 'OK', [(b'BODY[]', raw)]

    def logout(self):
        self.logged_out = True


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EmailPipelineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.owner = users.create_user(email='rh@example.test', password='test')
        cls.other = users.create_user(email='other@example.test', password='test')
        cls.candidate = users.create_user(email='candidate@example.test', password='test')
        cls.org = Organization.objects.create(account=cls.owner, name='Example')
        cls.other_org = Organization.objects.create(account=cls.other, name='Other')
        cls.category = JobCategory.objects.create(title='Developer')
        cls.offer = JobOffer.objects.create(company=cls.org, poste=cls.category, title='Developer', status='published')
        cls.foreign_offer = JobOffer.objects.create(company=cls.other_org, poste=cls.category, title='Other', status='published')
        cls.inbox = RecruitmentEmailInbox.objects.create(
            organization=cls.org, host='imap.example.test', username='rh@example.test',
            secret=encrypt_secret('app-password'), default_offer=cls.offer,
            enabled=True, verified_at=timezone.now(),
        )

    def setUp(self):
        self.media = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media.name + '/public', EMAIL_RESUME_ROOT=self.media.name + '/private')
        self.media_override.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.media_override.disable)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.owner)}')

    def raw_email(self, subject='Candidature développeur', *, attachment=True, sender='Candidate <candidate@example.test>'):
        message = EmailMessage()
        message['From'] = sender
        message['To'] = 'rh@example.test'
        message['Subject'] = subject
        message['Message-ID'] = '<application@example.test>'
        message.set_content('Bonjour, voici ma candidature.')
        if attachment:
            with fitz.open() as pdf:
                page = pdf.new_page()
                page.insert_text((72, 72), 'CV Python Django')
                content = pdf.tobytes()
            message.add_attachment(content, maintype='application', subtype='pdf', filename='../../CV.pdf')
        return message.as_bytes()

    def sync(self, raw=None, *, uid=1, validity=b'42'):
        connection = FakeIMAP({uid: raw or self.raw_email()}, validity)
        with patch('services.recruitment_email.open_inbox', return_value=connection):
            result = sync_inbox(self.inbox.pk)
        return result, connection

    def test_full_email_to_analysis_to_recruiter_flow(self):
        result, connection = self.sync()
        self.assertEqual(result['status'], 'synced')
        self.assertEqual(result['created'], 1)
        self.assertTrue(connection.logged_out)
        receipt = RecruitmentEmailMessage.objects.get()
        application = receipt.application
        self.assertEqual(application.source, 'email')
        self.assertEqual(application.job_offer, self.offer)
        self.assertEqual(application.applicant_email, 'candidate@example.test')
        self.assertNotIn('..', receipt.resume_file.name)
        self.assertFalse(application.resume)
        self.assertIn('private', receipt.resume_file.path)
        with self.assertRaises(ValueError):
            receipt.resume_file.url
        self.assertEqual(receipt.analysis_state, 'pending')
        self.assertNotIn('Bonjour', receipt.raw_secret)
        with patch('services.cv_analyzer.analyze_cv_pdf', return_value=AnalysisResponse(
                analyse='Profil Django pertinent, à valider par le recruteur.', accept=True, skills=['Django'])):
            self.assertEqual(analyze_pending_messages(), {'analyzed': 1})
        receipt.refresh_from_db()
        application.refresh_from_db()
        self.assertEqual(receipt.analysis_state, 'done')
        self.assertEqual(application.status, 'pending')
        self.assertTrue(application.needs_human_review)
        self.assertIsNotNone(application.match_score)
        self.assertEqual(ReviewNotification.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(type='new_application', related_application=application).count(), 1)
        response = self.client.get(f'/api/email-inboxes/{self.inbox.pk}/messages/')
        self.assertEqual(response.status_code, 200)
        rows = response.json().get('results', response.json())
        self.assertEqual(rows[0]['applicationId'], application.pk)
        self.assertEqual(rows[0]['analysisStatus'], 'done')
        self.assertTrue(rows[0]['needsHumanReview'])
        self.assertNotIn('rawSecret', str(response.json()))

    def test_private_resume_download_requires_owner_and_existing_serializers_expose_protected_url(self):
        from apps.jobs.serializers import JobApplicationSerializer, OrganizationApplicationSerializer
        self.sync()
        receipt = RecruitmentEmailMessage.objects.get()
        url = f'/api/email-inboxes/{self.inbox.pk}/messages/{receipt.pk}/resume/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        response.close()
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(JobApplicationSerializer(receipt.application).data['resume'], url)
        self.assertEqual(OrganizationApplicationSerializer(receipt.application).data['resumeUrl'], url)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.other)}')
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.credentials()
        self.assertEqual(self.client.get(url).status_code, 401)

    def test_original_email_is_preserved_and_downloadable_only_by_owner(self):
        raw = self.raw_email()
        self.sync(raw)
        receipt = RecruitmentEmailMessage.objects.get()
        url = f'/api/email-inboxes/{self.inbox.pk}/messages/{receipt.pk}/original/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, raw)
        self.assertIn('attachment', response['Content-Disposition'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.other)}')
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_automated_messages_and_platform_alerts_do_not_create_email_loops(self):
        for index, auto in enumerate([True, False]):
            message = EmailMessage()
            message['From'] = 'robot@example.test' if auto else 'platform@example.test'
            message['To'] = self.inbox.username
            message['Subject'] = 'Intervention requise'
            if auto:
                message['Auto-Submitted'] = 'auto-replied'
            message.set_content('Notification automatique')
            with override_settings(DEFAULT_FROM_EMAIL='Wiba <platform@example.test>'):
                receipt, _ = ingest_message(self.inbox, '42', index + 1, message.as_bytes())
            self.assertEqual(receipt.status, 'ignored')
        self.assertEqual(JobApplication.objects.count(), 0)
        self.assertEqual(ReviewNotification.objects.count(), 0)

    def test_negative_ai_recommendation_never_rejects_candidate_and_email_alert_setting_is_respected(self):
        from services.agent_workflow import dispatch_review_notification
        self.org.notify_blocking_cases = False
        self.org.save()
        self.sync()
        with patch('services.cv_analyzer.analyze_cv_pdf', return_value=AnalysisResponse(
                analyse='Compétences à vérifier.', accept=False, skills=[])):
            analyze_pending_messages()
        application = JobApplication.objects.get()
        self.assertEqual(application.status, 'pending')
        self.assertFalse(application.ai_decision)
        self.assertTrue(application.needs_human_review)
        with patch('services.agent_workflow.send_mail') as send:
            self.assertFalse(dispatch_review_notification(ReviewNotification.objects.get().pk))
            send.assert_not_called()

    def test_already_completed_analysis_is_not_repeated_after_worker_recovery(self):
        from apps.jobs.models import JobApplicationAnalysis
        self.sync()
        receipt = RecruitmentEmailMessage.objects.get()
        JobApplicationAnalysis.objects.create(application=receipt.application, status='done')
        with patch('services.cv_analyzer.analyze_job_application') as analyze:
            self.assertEqual(analyze_pending_messages(), {'analyzed': 1})
            analyze.assert_not_called()
        receipt.refresh_from_db()
        self.assertEqual(receipt.analysis_state, 'done')

    def test_reading_pending_analysis_does_not_start_another_ai_request(self):
        self.sync()
        application = JobApplication.objects.get()
        with patch('apps.jobs.views.analyze_job_application') as analyze:
            response = self.client.get(f'/api/jobs/applications/{application.pk}/extracted-data/')
        self.assertEqual(response.status_code, 202)
        analyze.assert_not_called()

    def test_preflight_command_and_container_shared_database_guard(self):
        from django.core.management.base import CommandError
        call_command('check_email_pipeline', stdout=StringIO())
        with patch('apps.jobs.management.commands.check_email_pipeline.connection.vendor', 'sqlite'), self.assertRaises(CommandError):
            call_command('check_email_pipeline', require_shared_database=True, stdout=StringIO())

    def test_private_storage_cannot_be_configured_under_public_media(self):
        from django.core.exceptions import ImproperlyConfigured
        from services.email_storage import RecruitmentResumeStorage
        with override_settings(MEDIA_ROOT=self.media.name, EMAIL_RESUME_ROOT=self.media.name + '/public'):
            with self.assertRaises(ImproperlyConfigured):
                RecruitmentResumeStorage().location

    def test_read_only_fetch_and_no_duplicate_even_after_uid_reset(self):
        raw = self.raw_email()
        first, connection = self.sync(raw)
        self.assertEqual(first['created'], 1)
        second, _ = self.sync(raw)
        third, _ = self.sync(raw, uid=8, validity=b'43')
        self.assertEqual(second['processed'], 0)
        self.assertEqual(third['created'], 0)
        self.assertEqual(JobApplication.objects.count(), 1)
        self.assertEqual(RecruitmentEmailMessage.objects.count(), 1)
        self.assertTrue(any(args[-1] == '(BODY.PEEK[])' for command, args in connection.calls if command == 'fetch'))
        self.assertTrue(all(command in ('search', 'fetch') for command, _ in connection.calls))

    def test_unassigned_message_is_preserved_then_manually_assigned(self):
        self.inbox.default_offer = None
        self.inbox.save()
        result, _ = self.sync()
        self.assertEqual(result['unassigned'], 1)
        self.assertEqual(JobApplication.objects.count(), 0)
        receipt = RecruitmentEmailMessage.objects.get()
        self.assertTrue(decrypt_secret(receipt.raw_secret))
        response = self.client.post(f'/api/email-inboxes/{self.inbox.pk}/messages/{receipt.pk}/assign/',
                                    {'offerId': self.offer.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.json()['status'], 'imported')
        repeated = self.client.post(f'/api/email-inboxes/{self.inbox.pk}/messages/{receipt.pk}/assign/',
                                    {'offerId': self.offer.pk}, format='json')
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_foreign_or_ambiguous_tags_never_fall_back_to_default(self):
        for subject in [f'[JOB-{self.foreign_offer.pk}]', f'[ORG-{self.other_org.pk}][JOB-{self.offer.pk}]',
                        f'[JOB-{self.offer.pk}][JOB-{self.foreign_offer.pk}]']:
            self.assertIsNone(choose_offer(self.inbox, subject))
        self.assertEqual(choose_offer(self.inbox, f'[ORG-{self.org.pk}][JOB-{self.offer.pk}]'), self.offer)

    def test_closed_offer_requires_human_assignment(self):
        self.offer.status = 'draft'
        self.offer.save()
        self.assertIsNone(choose_offer(self.inbox, 'Candidature'))
        result, _ = self.sync()
        self.assertEqual(result['unassigned'], 1)

    def test_missing_resume_keeps_application_and_requests_human_review(self):
        result, _ = self.sync(self.raw_email(attachment=False))
        self.assertEqual(result['created'], 1)
        receipt = RecruitmentEmailMessage.objects.get()
        self.assertEqual(receipt.error_code, 'missing_or_unsupported_resume')
        self.assertTrue(receipt.application.needs_human_review)
        self.assertEqual(receipt.analysis_state, 'manual')

    @override_settings(USE_CELERY_FOR_CV_ANALYSIS=False)
    def test_manual_analysis_of_private_resume_clears_failed_queue_state(self):
        self.sync()
        receipt = RecruitmentEmailMessage.objects.get()
        receipt.analysis_state = 'failed'
        receipt.error_code = 'analysis_failed'
        receipt.save()
        with patch('services.cv_analyzer.analyze_cv_pdf', return_value=AnalysisResponse(analyse='Analyse manuelle terminée.', accept=True)):
            response = self.client.post(f'/api/jobs/applications/{receipt.application_id}/analyze/')
        self.assertEqual(response.status_code, 200)
        receipt.refresh_from_db()
        self.assertEqual(receipt.analysis_state, 'done')
        self.assertEqual(receipt.error_code, '')

    def test_ambiguous_pdf_attachments_are_not_arbitrarily_chosen(self):
        with fitz.open() as pdf:
            pdf.new_page()
            content = pdf.tobytes()
        message = EmailMessage()
        message['From'] = 'candidate@example.test'
        message['Subject'] = 'Candidature'
        message.set_content('Voici mes documents.')
        for filename in ['CV-version-1.pdf', 'CV-version-2.pdf']:
            message.add_attachment(content, maintype='application', subtype='pdf', filename=filename)
        receipt, _ = ingest_message(self.inbox, '42', 1, message.as_bytes())
        self.assertEqual(receipt.error_code, 'missing_or_unsupported_resume')
        self.assertTrue(receipt.application.needs_human_review)
        self.assertFalse(receipt.resume_file)

    def test_invalid_sender_is_retained_without_poisoning_the_sync(self):
        result, _ = self.sync(self.raw_email(sender='invalid'))
        self.assertEqual(result['status'], 'synced')
        receipt = RecruitmentEmailMessage.objects.get()
        self.assertEqual(receipt.error_code, 'invalid_sender')
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_oversized_message_is_reported_without_fetching_its_body(self):
        connection = FakeIMAP({1: b'x' * 12})
        original = connection.uid
        def oversized(command, *args):
            if command == 'fetch' and args[-1] == '(RFC822.SIZE)':
                return 'OK', [b'1 (RFC822.SIZE 99999999)']
            return original(command, *args)
        with patch('services.recruitment_email.open_inbox', return_value=connection), patch.object(connection, 'uid', side_effect=oversized):
            self.assertEqual(sync_inbox(self.inbox.pk)['status'], 'synced')
        self.assertEqual(RecruitmentEmailMessage.objects.get().error_code, 'message_too_large')
        self.assertFalse(any(args[-1] == '(BODY.PEEK[])' for command, args in connection.calls if command == 'fetch'))

    def test_disabling_analysis_preserves_import_and_manual_analysis(self):
        self.org.auto_analyze_applications = False
        self.org.save()
        self.sync()
        receipt = RecruitmentEmailMessage.objects.get()
        self.assertEqual(receipt.analysis_state, 'manual')
        with patch('services.cv_analyzer.analyze_job_application') as analyze:
            self.assertEqual(analyze_pending_messages(), {'analyzed': 0})
            analyze.assert_not_called()

    def test_disabling_analysis_after_import_suspends_pending_work(self):
        self.sync()
        self.org.auto_analyze_applications = False
        self.org.save()
        with patch('services.cv_analyzer.analyze_job_application') as analyze:
            analyze_pending_messages()
            analyze.assert_not_called()
        self.assertEqual(RecruitmentEmailMessage.objects.get().analysis_state, 'pending')

    def test_analysis_failures_are_retried_and_final_failure_needs_review(self):
        self.sync()
        receipt = RecruitmentEmailMessage.objects.get()
        with patch('services.cv_analyzer.analyze_job_application', side_effect=RuntimeError('private-data')):
            for attempt in range(5):
                RecruitmentEmailMessage.objects.filter(pk=receipt.pk).update(analysis_next_attempt_at=None)
                analyze_pending_messages()
                receipt.refresh_from_db()
                self.assertEqual(receipt.analysis_attempts, attempt + 1)
        self.assertEqual(receipt.analysis_state, 'failed')
        self.assertTrue(receipt.application.needs_human_review)
        self.assertNotIn('private-data', str(list(AgentEvent.objects.values('input_data'))))

    def test_expired_worker_lease_is_recovered(self):
        self.sync()
        receipt = RecruitmentEmailMessage.objects.get()
        receipt.analysis_state = 'processing'
        receipt.analysis_locked_until = timezone.now() - timedelta(seconds=1)
        receipt.analysis_attempts = 5
        receipt.save()
        self.assertEqual(analyze_pending_messages(), {'analyzed': 0})
        receipt.refresh_from_db()
        self.assertEqual(receipt.analysis_state, 'failed')
        self.assertTrue(receipt.application.needs_human_review)

    def test_sync_failure_is_sanitized_and_releases_lease_for_retry(self):
        with patch('services.recruitment_email.open_inbox', side_effect=RuntimeError('app-password')):
            result = sync_inbox(self.inbox.pk)
        self.assertEqual(result['errorCode'], 'sync_failed')
        self.inbox.refresh_from_db()
        self.assertIsNone(self.inbox.locked_until)
        self.assertGreater(self.inbox.next_sync_at, timezone.now())
        self.assertNotIn('app-password', str(result))
        result, _ = self.sync()
        self.assertEqual(result['created'], 1)

    def test_parallel_sync_is_skipped_and_disabled_connections_are_not_read(self):
        self.inbox.locked_until = timezone.now() + timedelta(minutes=5)
        self.inbox.save()
        with patch('services.recruitment_email.open_inbox') as connect:
            self.assertEqual(sync_inbox(self.inbox.pk)['status'], 'busy_or_disabled')
            connect.assert_not_called()
        self.inbox.locked_until = None
        self.inbox.enabled = False
        self.inbox.save()
        with patch('services.recruitment_email.open_inbox') as connect:
            sync_inbox(self.inbox.pk)
            connect.assert_not_called()

    def test_connection_create_test_enable_and_secret_rotation(self):
        data = {'host': 'imap.gmail.com', 'username': 'jobs@example.test', 'password': 'an-app-password',
                'folder': 'Recruitment', 'defaultOffer': self.offer.pk}
        response = self.client.post('/api/email-inboxes/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        inbox = RecruitmentEmailInbox.objects.get(pk=response.json()['id'])
        self.assertFalse(inbox.enabled)
        self.assertNotEqual(inbox.secret, data['password'])
        self.assertNotIn('password', response.json())
        url = f'/api/email-inboxes/{inbox.pk}/'
        self.assertEqual(self.client.patch(url, {'enabled': True}, format='json').status_code, 400)
        connection = MagicMock()
        connection.select.return_value = ('OK', [b'0'])
        with patch('services.recruitment_email.PublicIMAP', return_value=connection):
            response = self.client.post(url + 'test/')
        self.assertEqual(response.status_code, 200, response.data)
        connection.select.assert_called_once_with('"Recruitment"', readonly=True)
        self.assertEqual(self.client.patch(url, {'enabled': True}, format='json').status_code, 200)
        response = self.client.patch(url, {'password': 'rotated-app-password'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['enabled'])
        self.assertIsNone(response.json()['verifiedAt'])
        inbox.refresh_from_db()
        self.assertEqual(decrypt_secret(inbox.secret), 'rotated-app-password')
        self.assertNotIn('rotated-app-password', str(list(AgentEvent.objects.values('input_data'))))

    def test_connection_fields_and_cross_organization_offer_are_validated(self):
        base = {'host': 'imap.gmail.com', 'username': 'jobs@example.test', 'password': 'app-password'}
        for extra in [{'defaultOffer': self.foreign_offer.pk}, {'host': 'https://imap.gmail.com'},
                      {'folder': 'INBOX\r\nLOGOUT'}, {'enabled': 'false'}]:
            response = self.client.post('/api/email-inboxes/', {**base, **extra}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.client.patch(f'/api/email-inboxes/{self.inbox.pk}/', {'host': 'another.test'}, format='json').status_code, 400)

    def test_tenant_isolation_for_all_mailbox_actions_and_assignment(self):
        self.inbox.default_offer = None
        self.inbox.save()
        self.sync()
        receipt = RecruitmentEmailMessage.objects.get()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.other)}')
        url = f'/api/email-inboxes/{self.inbox.pk}/'
        for method, suffix, body in [('get', '', None), ('patch', '', {'enabled': False}),
                                     ('post', 'test/', {}), ('post', 'sync/', {}), ('get', 'messages/', None),
                                     ('post', f'messages/{receipt.pk}/assign/', {'offerId': self.foreign_offer.pk})]:
            response = getattr(self.client, method)(url + suffix, body, format='json')
            self.assertEqual(response.status_code, 404, (method, suffix, response.data))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.owner)}')
        response = self.client.post(url + f'messages/{receipt.pk}/assign/', {'offerId': self.foreign_offer.pk}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_candidate_cannot_create_connection_and_missing_jwt_is_rejected(self):
        self.client.credentials()
        self.assertEqual(self.client.get('/api/email-inboxes/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.candidate)}')
        response = self.client.post('/api/email-inboxes/', {
            'host': 'imap.gmail.com', 'username': 'jobs@example.test', 'password': 'app-password'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_sync_endpoint_reports_broker_failure_without_losing_request(self):
        url = f'/api/email-inboxes/{self.inbox.pk}/sync/'
        with patch('apps.jobs.tasks.sync_recruitment_inbox.delay', side_effect=RuntimeError('broker-credentials')):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 503)
        self.inbox.refresh_from_db()
        self.assertIsNotNone(self.inbox.next_sync_at)
        self.assertEqual(self.inbox.error_code, 'queue_unavailable')
        self.assertNotIn('broker-credentials', str(response.json()))

    def test_legacy_sync_endpoint_only_queues_own_connections(self):
        RecruitmentEmailInbox.objects.create(organization=self.other_org, host='imap.example.test', username='other',
                                             secret=encrypt_secret('test'), enabled=True, verified_at=timezone.now())
        with patch('apps.jobs.tasks.sync_recruitment_inbox.delay') as queue:
            response = self.client.post('/api/jobs/applications/sync-email-applications/')
        self.assertEqual(response.status_code, 202, response.data)
        queue.assert_called_once_with(self.inbox.pk)

    def test_command_runs_without_broker_and_scopes_organization(self):
        connection = FakeIMAP({1: self.raw_email()})
        with patch('services.recruitment_email.open_inbox', return_value=connection):
            output = StringIO()
            call_command('import_email_applications', organization=self.org.pk, stdout=output)
        self.assertEqual(JobApplication.objects.count(), 1)
        self.assertIn('synced', output.getvalue())

    def test_scheduler_queues_only_due_verified_enabled_connections(self):
        from apps.jobs.tasks import sync_recruitment_inboxes
        RecruitmentEmailInbox.objects.create(organization=self.other_org, host='imap.example.test', username='off',
                                             secret=encrypt_secret('test'), enabled=False)
        with patch('apps.jobs.tasks.sync_recruitment_inbox.apply_async') as queue:
            self.assertEqual(sync_recruitment_inboxes.run(), {'queued': 1})
        queue.assert_called_once_with(args=[self.inbox.pk], expires=300)

    def test_private_and_mixed_dns_addresses_are_blocked(self):
        for addresses in [['127.0.0.1'], ['10.0.0.1'], ['169.254.169.254'], ['::1'], ['8.8.8.8', '127.0.0.1']]:
            with self.subTest(addresses=addresses), patch('socket.getaddrinfo', return_value=[
                    (2, 1, 6, '', (address, 993)) for address in addresses]):
                with self.assertRaises(MailboxError):
                    public_address('imap.example.test')

    def test_socket_uses_pinned_public_ip_and_original_tls_hostname(self):
        client = object.__new__(PublicIMAP)
        client.host = 'imap.example.test'
        client.port = 993
        client.ssl_context = MagicMock()
        with patch('services.recruitment_email.public_address', return_value='8.8.8.8'), patch('socket.create_connection') as connect:
            client._create_socket(15)
        connect.assert_called_once_with(('8.8.8.8', 993), timeout=15)
        client.ssl_context.wrap_socket.assert_called_once_with(connect.return_value, server_hostname='imap.example.test')
