from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.evaluations.models import Candidate, Evaluation, EvaluationInvitation, Participant
from apps.jobs.models import (
    AgentEvent, ComplianceRequest, ContractOTP, InterviewBooking, JobApplication,
    JobCategory, JobOffer, ReviewNotification, OnboardingPlan,
)
from apps.organizations.models import Organization
from services.agent_workflow import dispatch_review_notification, set_human_review
from services.recruitment_decisions import change_application_status


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AgentAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.recruiter = users.create_user(email='rh@example.test', password='test')
        cls.other = users.create_user(email='other@example.test', password='test')
        cls.candidate = users.create_user(email='candidate@example.test', password='test')
        cls.organization = Organization.objects.create(account=cls.recruiter, name='Company')
        cls.other_org = Organization.objects.create(account=cls.other, name='Other')
        category = JobCategory.objects.create(title='Developer')
        cls.offer = JobOffer.objects.create(company=cls.organization, poste=category, title='Developer')
        cls.application = JobApplication.objects.create(job_offer=cls.offer, user=cls.candidate,
            applicant_name='Candidate', applicant_email=cls.candidate.email)

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def login(self, user=None):
        self.client.force_authenticate(user=user or self.recruiter)

    def review(self):
        return set_human_review(self.application.pk, reason='Validation requise')

    def test_review_deduplicates_email_and_audit(self):
        self.review()
        self.review()
        notice = ReviewNotification.objects.get()
        self.assertTrue(dispatch_review_notification(notice.pk))
        self.assertFalse(dispatch_review_notification(notice.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.recruiter.email])
        self.assertNotIn(self.candidate.email, mail.outbox[0].body)
        self.assertEqual(AgentEvent.objects.filter(action='review.required').count(), 1)

    def test_review_reminder_is_bounded_and_stops_after_resolution(self):
        self.review()
        notice = ReviewNotification.objects.get()
        for _ in range(3):
            ReviewNotification.objects.filter(pk=notice.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            self.assertTrue(dispatch_review_notification(notice.pk))
        ReviewNotification.objects.filter(pk=notice.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(dispatch_review_notification(notice.pk))
        self.assertEqual(len(mail.outbox), 3)
        set_human_review(self.application.pk, reason='Résolu', actor=self.recruiter, required=False)
        self.assertFalse(dispatch_review_notification(notice.pk))

    def test_dispatch_command_ignores_old_review_generation(self):
        from django.core.management import call_command
        from io import StringIO

        self.review()
        set_human_review(self.application.pk, reason='Résolu', actor=self.recruiter, required=False)
        self.review()
        call_command('send_review_notifications', stdout=StringIO())
        call_command('send_review_notifications', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ReviewNotification.objects.filter(sent_count=1).count(), 1)

    def test_missing_resume_creates_real_review_without_calling_ai(self):
        from services.cv_analyzer import analyze_job_application

        self.application.user = None
        analyze_job_application(self.application, self.offer)
        self.application.refresh_from_db()
        self.assertTrue(self.application.needs_human_review)
        self.assertEqual(self.application.analysis.error, 'no_resume_or_profile')
        self.assertEqual(ReviewNotification.objects.count(), 1)

    def test_organization_console_filters_real_blockers(self):
        self.login()
        self.assertEqual(self.client.get('/api/jobs/applications/organization/?needsHumanReview=true').json()['count'], 0)
        self.review()
        response = self.client.get('/api/jobs/applications/organization/?needsHumanReview=true')
        self.assertEqual(response.json()['count'], 1)
        self.assertTrue(response.json()['results'][0]['needsHumanReview'])

    def test_notification_retry_on_smtp_failure(self):
        self.review()
        notice = ReviewNotification.objects.get()
        with patch('services.agent_workflow.send_mail', side_effect=RuntimeError('secret')):
            self.assertFalse(dispatch_review_notification(notice.pk))
        notice.refresh_from_db()
        self.assertEqual(notice.error_code, 'delivery_failed')
        self.assertIsNone(notice.sent_at)
        self.assertIsNotNone(notice.next_attempt_at)

    def test_resolved_review_stops_email(self):
        self.review()
        change_application_status(application_id=self.application.pk, actor=self.recruiter, target='shortlisted')
        self.application.refresh_from_db()
        self.assertFalse(self.application.needs_human_review)
        self.assertFalse(dispatch_review_notification(ReviewNotification.objects.get().pk))
        self.assertEqual(len(mail.outbox), 0)

    def test_candidate_cannot_escalate(self):
        self.login(self.candidate)
        response = self.client.post(f'/api/jobs/applications/{self.application.pk}/human-review/', {'reason': 'Review'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_recruiter_can_escalate_and_filter(self):
        self.login()
        response = self.client.post(f'/api/jobs/applications/{self.application.pk}/human-review/', {'reason': 'Review'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['needsHumanReview'])
        response = self.client.get('/api/jobs/applications/?needsHumanReview=true')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['results'][0]['needsHumanReview'])
        self.assertEqual(self.client.get('/api/jobs/applications/?needsHumanReview=false').json()['count'], 0)

    def test_audit_and_events_are_tenant_scoped(self):
        self.review()
        self.login(self.other)
        self.assertEqual(self.client.get('/api/audit/').json()['count'], 0)
        self.login()
        audit = self.client.get('/api/audit/').json()
        self.assertEqual(audit['count'], 1)
        event = audit['results'][0]
        self.assertEqual(event['actor'], 'agent')
        self.assertNotIn('email', str(event['inputData']))
        self.assertEqual(self.client.get('/api/agent/events/', {'after_id': event['id']}).json()['count'], 0)
        self.login(self.candidate)
        self.assertEqual(self.client.get('/api/audit/').status_code, 403)

    def test_stats_use_actual_signed_contract_dates(self):
        self.login()
        self.review()
        stats = self.client.get('/api/jobs/applications/dashboard-stats/').json()
        self.assertEqual(stats['totalApplications'], 1)
        self.assertEqual(stats['needsHumanReview'], 1)
        self.assertIsNone(stats['averageDaysToSignedContract'])
        self.login(self.other)
        self.assertEqual(self.client.get('/api/jobs/applications/dashboard-stats/').json()['totalApplications'], 0)

    def test_consent_is_self_service_and_audited(self):
        self.login(self.candidate)
        response = self.client.patch('/api/compliance/consents/', {
            'organization': self.organization.pk, 'purpose': 'talent_pool', 'granted': True,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user'], self.candidate.pk)
        self.assertEqual(AgentEvent.objects.get().action, 'consent.updated')
        response = self.client.patch('/api/compliance/consents/', {
            'organization': self.other_org.pk, 'purpose': 'talent_pool', 'granted': True,
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_deletion_requests_are_pending_not_falsely_completed(self):
        self.login(self.candidate)
        for _ in range(2):
            response = self.client.post('/api/compliance/deletion-requests/', {'organization': self.organization.pk}, format='json')
            self.assertIn(response.status_code, [200, 201])
            self.assertEqual(response.json()['status'], 'pending')
        self.assertEqual(ComplianceRequest.objects.count(), 1)
        self.assertTrue(get_user_model().objects.filter(pk=self.candidate.pk).exists())
        self.login(self.other)
        self.assertEqual(self.client.get('/api/compliance/deletion-requests/').json(), [])

    def test_retention_policy_requires_organization_and_valid_durations(self):
        self.login(self.candidate)
        self.assertEqual(self.client.get('/api/compliance/retention-policy/').status_code, 403)
        self.login()
        self.assertFalse(self.client.get('/api/compliance/retention-policy/').json()['configured'])
        response = self.client.put('/api/compliance/retention-policy/', {'candidateDays': 180, 'talentPoolDays': 365}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['candidateDays'], 180)
        self.assertEqual(self.client.put('/api/compliance/retention-policy/', {'candidateDays': -1, 'talentPoolDays': 365}, format='json').status_code, 400)

    def booking(self, application=None):
        self.login()
        start = timezone.now() + timedelta(days=2)
        response = self.client.post(f'/api/jobs/applications/{(application or self.application).pk}/interview-booking/', {
            'slots': [{'startsAt': start.isoformat(), 'endsAt': (start + timedelta(hours=1)).isoformat()}],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.json()['token']

    def test_public_booking_is_single_use_and_updates_interview(self):
        token = self.booking()
        self.client.force_authenticate(user=None)
        response = self.client.get(f'/api/jobs/interview-booking/{token}/')
        self.assertEqual(response.status_code, 200)
        slot = response.json()['slots'][0]['id']
        response = self.client.post(f'/api/jobs/interview-slots/{token}/book/', {'slotId': slot}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(f'/api/jobs/interview-slots/{token}/book/', {'slotId': slot}, format='json').status_code, 409)
        self.application.refresh_from_db()
        self.assertEqual(self.application.interview_duration, 60)
        self.assertNotEqual(InterviewBooking.objects.get().token_hash, token)

    def test_overlapping_booking_is_rejected(self):
        first = self.booking()
        second = self.booking()
        self.client.force_authenticate(user=None)
        slot1 = self.client.get(f'/api/jobs/interview-slots/{first}/').json()['slots'][0]['id']
        slot2 = self.client.get(f'/api/jobs/interview-slots/{second}/').json()['slots'][0]['id']
        self.assertEqual(self.client.post(f'/api/jobs/interview-slots/{first}/book/', {'slotId': slot1}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/jobs/interview-slots/{second}/book/', {'slotId': slot2}, format='json').status_code, 409)

    def test_stats_calculate_signed_contract_duration(self):
        JobApplication.objects.filter(pk=self.application.pk).update(
            status='accepted', contract_signed_at=self.application.submitted_at + timedelta(days=2),
        )
        self.login()
        stats = self.client.get('/api/jobs/applications/dashboard-stats/').json()
        self.assertEqual(stats['averageDaysToSignedContract'], 2.0)
        self.assertEqual(stats['acceptedConversionRate'], 1.0)

    def test_expired_booking_is_rejected(self):
        token = self.booking()
        InterviewBooking.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f'/api/jobs/interview-slots/{token}/').status_code, 404)

    def test_foreign_slot_is_rejected(self):
        token = self.booking()
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post(f'/api/jobs/interview-slots/{token}/book/', {'slotId': 99999}, format='json').status_code, 404)

    def setup_contract(self):
        JobApplication.objects.filter(pk=self.application.pk).update(
            contract_token='contract-secret-token', contract_token_expires_at=timezone.now() + timedelta(days=1),
            contract_status='sent', contract_file='contracts/test.pdf',
        )
        return '/api/jobs/contract/contract-secret-token/'

    def test_otp_is_hashed_rate_limited_and_single_use(self):
        url = self.setup_contract()
        response = self.client.post(url + 'request-otp/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        code = re.search(r'\b\d{6}\b', mail.outbox[0].body).group()
        self.assertNotEqual(ContractOTP.objects.get().code_hash, code)
        self.assertEqual(self.client.post(url + 'request-otp/', {}, format='json').status_code, 429)
        self.assertEqual(self.client.post(url + 'verify-otp/', {'code': code}, format='json').status_code, 200)
        self.assertEqual(self.client.post(url + 'verify-otp/', {'code': code}, format='json').status_code, 409)

    def test_otp_failure_attempts_are_persisted(self):
        url = self.setup_contract()
        self.client.post(url + 'request-otp/', {}, format='json')
        for _ in range(5):
            self.assertEqual(self.client.post(url + 'verify-otp/', {'code': 'invalid'}, format='json').status_code, 400)
        self.assertEqual(ContractOTP.objects.get().attempts, 5)
        self.assertEqual(self.client.post(url + 'verify-otp/', {'code': '000000'}, format='json').status_code, 429)

    def test_otp_expiration_and_rotated_token(self):
        url = self.setup_contract()
        self.client.post(url + 'request-otp/', {}, format='json')
        ContractOTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(url + 'verify-otp/', {'code': '000000'}, format='json').status_code, 400)
        JobApplication.objects.filter(pk=self.application.pk).update(contract_token='rotated')
        self.assertEqual(self.client.post(url + 'request-otp/', {}, format='json').status_code, 404)

    def test_verified_otp_allows_one_pdf_upload(self):
        JobApplication.objects.filter(pk=self.application.pk).update(status='accepted')
        url = self.setup_contract()
        self.client.post(url + 'request-otp/', {}, format='json')
        code = re.search(r'\b\d{6}\b', mail.outbox[0].body).group()
        self.client.post(url + 'verify-otp/', {'code': code}, format='json')
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(url + 'upload-signed/', {
                'signed_contract_file': SimpleUploadedFile('signed.pdf', b'%PDF-1.4\nexample', content_type='application/pdf'),
            }, format='multipart')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(self.client.post(url + 'upload-signed/', {}, format='multipart').status_code, 404)
        self.application.refresh_from_db()
        self.assertEqual(self.application.contract_status, 'signed')
        self.assertEqual(AgentEvent.objects.get(action='contract.signed_pdf_received').actor, 'human')
        self.assertTrue(OnboardingPlan.objects.filter(application=self.application).exists())

    def test_otp_smtp_failure_does_not_create_challenge(self):
        url = self.setup_contract()
        with patch('apps.jobs.agent_api.send_mail', side_effect=RuntimeError('private smtp error')):
            response = self.client.post(url + 'request-otp/', {}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private smtp error', str(response.data))
        self.assertFalse(ContractOTP.objects.exists())

    def test_onboarding_get_is_read_only_and_tenant_scoped(self):
        self.login()
        url = f'/api/jobs/applications/{self.application.pk}/onboarding/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['eligible'])
        self.assertEqual(response.json()['version'], 0)
        self.assertEqual(len(response.json()['steps']), 5)
        self.assertFalse(OnboardingPlan.objects.exists())
        self.login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_onboarding_patch_requires_acceptance_and_version(self):
        self.login()
        url = f'/api/jobs/applications/{self.application.pk}/onboarding/'
        data = {'expectedVersion': 0, 'objectives': {'day30': [{'title': 'Formation initiale', 'status': 'pending'}]}}
        self.assertEqual(self.client.patch(url, data, format='json').status_code, 400)
        self.assertFalse(OnboardingPlan.objects.exists())
        JobApplication.objects.filter(pk=self.application.pk).update(status='accepted')
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.json()['version'], 1)
        self.assertEqual(response.json()['objectives']['day30'][0]['title'], 'Formation initiale')
        self.assertEqual(response.json()['objectives']['day60'], [])
        self.assertEqual(self.client.patch(url, data, format='json').status_code, 409)
        self.assertEqual(AgentEvent.objects.filter(action='onboarding.updated').count(), 1)

    def test_candidate_can_read_but_not_modify_own_onboarding(self):
        JobApplication.objects.filter(pk=self.application.pk).update(status='accepted')
        self.login(self.candidate)
        url = f'/api/jobs/applications/{self.application.pk}/onboarding/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'expectedVersion': 0, 'startDate': '2027-01-10'}, format='json').status_code, 403)

    def test_onboarding_distinguishes_declaration_from_real_document(self):
        JobApplication.objects.filter(pk=self.application.pk).update(status='accepted')
        self.login()
        url = f'/api/jobs/applications/{self.application.pk}/onboarding/'
        response = self.client.patch(url, {'expectedVersion': 0, 'administrativeDocuments': [
            {'kind': 'identity_document', 'status': 'declared_received'},
        ]}, format='json')
        self.assertEqual(response.status_code, 200)
        documents = {item['kind']: item for item in response.json()['administrativeDocuments']}
        self.assertEqual(documents['signed_contract']['status'], 'missing')
        self.assertEqual(documents['identity_document']['source'], 'human')
        self.assertEqual(documents['identity_document']['status'], 'declared_received')
        self.assertEqual(self.client.patch(url, {'expectedVersion': 1, 'administrativeDocuments': [
            {'kind': 'identity_document', 'status': 'verified'},
        ]}, format='json').status_code, 400)

    def test_onboarding_rejects_duplicate_step_ids(self):
        JobApplication.objects.filter(pk=self.application.pk).update(status='accepted')
        self.login()
        response = self.client.patch(f'/api/jobs/applications/{self.application.pk}/onboarding/', {
            'expectedVersion': 0, 'steps': [
                {'id': 'welcome', 'title': 'Accueil', 'status': 'pending'},
                {'id': 'welcome', 'title': 'Accueil bis', 'status': 'completed'},
            ],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(OnboardingPlan.objects.exists())

    def test_signed_upload_requires_otp(self):
        url = self.setup_contract()
        self.assertEqual(self.client.post(url + 'upload-signed/', {}, format='multipart').status_code, 403)

    def test_verify_invitation_route_does_not_create_participant(self):
        evaluation = Evaluation.objects.create(title='Technical', publisher=self.recruiter)
        candidate = Candidate.objects.create(email=self.candidate.email, full_name='Candidate', owner=self.recruiter)
        invitation = EvaluationInvitation.objects.create(evaluation=evaluation, candidate=candidate,
            expires_at=timezone.now() + timedelta(days=1))
        response = self.client.post('/api/evaluations/sessions/verify_invitation', {'token': invitation.token}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['evaluationId'], evaluation.pk)
        self.assertFalse(Participant.objects.exists())
        invitation.expires_at = timezone.now() - timedelta(seconds=1)
        invitation.save()
        self.assertEqual(self.client.post('/api/evaluations/sessions/verify_invitation/', {'token': invitation.token}, format='json').status_code, 403)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OrganizationChannelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(email='org-channels@example.test', password='test')
        cls.org = Organization.objects.create(account=cls.user, name='OrgChannels')
        cls.category = JobCategory.objects.create(title='Dev')
        cls.offer = JobOffer.objects.create(company=cls.org, poste=cls.category, title='Dev',
                                            description='d', requirements='r', job_type='cdi',
                                            experience_level='junior', location='Douala')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_channel_fields_accepted_in_camel_case_and_filtered(self):
        response = self.client.patch(f'/api/organizations/{self.org.pk}/', {
            'preferredChannels': ['linkedin', 'canal_inconnu', 'site_carriere', 'linkedin'],
            'linkedinPageUrl': 'https://linkedin.com/company/org',
            'emploiCmAccount': 'org-cm',
            'hrAlertEmail': 'rh@org.test',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        data = response.json()
        self.assertEqual(data['preferredChannels'], ['linkedin', 'site_carriere'])
        self.assertEqual(data['linkedinPageUrl'], 'https://linkedin.com/company/org')
        self.assertEqual(data['emploiCmAccount'], 'org-cm')
        self.assertEqual(data['hrAlertEmail'], 'rh@org.test')

    def test_empty_channel_list_and_missing_fields_do_not_error(self):
        response = self.client.patch(f'/api/organizations/{self.org.pk}/', {'preferredChannels': []}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['preferredChannels'], [])

    def test_invalid_email_and_url_are_rejected(self):
        response = self.client.patch(f'/api/organizations/{self.org.pk}/', {'hrAlertEmail': 'pas-un-email'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_distribution_uses_preferred_channels_and_site_carriere_always_present(self):
        self.org.preferred_channels = ['linkedin']
        self.org.save()
        response = self.client.post(f'/api/jobs/offers/{self.offer.pk}/distribute/', {}, format='json')
        states = {c['name']: c['state'] for c in response.json()['channels']}
        self.assertEqual(states['site_carriere'], 'published')
        self.assertEqual(states['linkedin'], 'failed')
        self.assertNotIn('emploi_cm', states)

    def test_linkedin_missing_page_is_explicit_failure(self):
        self.org.preferred_channels = ['linkedin']
        self.org.save()
        with patch.dict('os.environ', {'LINKEDIN_API_TOKEN': 'token-test'}):
            response = self.client.post(f'/api/jobs/offers/{self.offer.pk}/distribute/', {'channels': ['linkedin']}, format='json')
        channel = response.json()['channels'][0]
        self.assertEqual(channel['state'], 'failed')
        self.assertIn('linkedinPageUrl', channel['error'])

    def test_review_email_routes_to_hr_alert_email(self):
        self.org.hr_alert_email = 'alertes-rh@org.test'
        self.org.save()
        application = JobApplication.objects.create(job_offer=self.offer, applicant_name='C', applicant_email='c@x.test')
        set_human_review(application.pk, reason='Vérification requise')
        notice = ReviewNotification.objects.get(application=application)
        self.assertTrue(dispatch_review_notification(notice.pk))
        self.assertEqual(mail.outbox[0].to, ['alertes-rh@org.test'])
        event = AgentEvent.objects.filter(action='review.email_submitted').latest('timestamp')
        self.assertEqual(event.input_data['recipient'], 'alertes-rh@org.test')
