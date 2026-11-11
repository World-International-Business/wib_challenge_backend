from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.jobs.models import JobApplication, JobCategory, JobOffer
from apps.organizations.models import Organization
from services.recruitment_decisions import change_application_status


class RecruitmentDecisionTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.recruiter = users.create_user(email='recruiter@example.test', password='test-password')
        self.candidate = users.create_user(email='candidate@example.test', password='test-password')
        self.outsider = users.create_user(email='outsider@example.test', password='test-password')
        organization = Organization.objects.create(name='Company', account=self.recruiter)
        category = JobCategory.objects.create(title='Developer')
        offer = JobOffer.objects.create(company=organization, poste=category, title='Developer')
        self.application = JobApplication.objects.create(
            job_offer=offer, user=self.candidate,
            applicant_name='Candidate', applicant_email=self.candidate.email,
        )

    def test_api_candidate_cannot_change_own_status(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.jobs.views import JobApplicationViewSet

        request = APIRequestFactory().patch('/', {'status': 'accepted'}, format='json')
        force_authenticate(request, user=self.candidate)
        response = JobApplicationViewSet.as_view({'patch': 'update_status'})(
            request, pk=self.application.pk,
        )
        self.assertEqual(response.status_code, 403)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'pending')

    def test_candidate_cannot_decide(self):
        with self.assertRaises(PermissionDenied):
            self.decide(self.candidate)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'pending')
        self.assertFalse(self.application.decision_events.exists())

    def test_other_organization_cannot_decide(self):
        Organization.objects.create(name='Other', account=self.outsider)
        with self.assertRaises(PermissionDenied):
            self.decide(self.outsider)

    def test_recruiter_decision_is_audited(self):
        self.decide(self.recruiter)
        event = self.application.decision_events.get()
        self.assertEqual(event.actor_id, self.recruiter.pk)
        self.assertEqual(event.from_status, 'pending')
        self.assertEqual(event.to_status, 'shortlisted')
        self.assertTrue(event.created_at)
        self.assertEqual(event.policy_version, 'human-decisions-v1')

    def test_repeat_status_does_not_duplicate_audit(self):
        self.decide(self.recruiter)
        self.decide(self.recruiter)
        self.assertEqual(self.application.decision_events.count(), 1)

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.decide(self.recruiter, 'unknown')
        self.assertFalse(self.application.decision_events.exists())

    def test_acceptance_requires_shortlist(self):
        with self.assertRaises(ValidationError):
            change_application_status(application_id=self.application.pk, actor=self.recruiter,
                                      target='accepted', reason='Approved')
        self.assertFalse(self.application.decision_events.exists())

    def test_rejection_requires_reason(self):
        with self.assertRaises(ValidationError):
            self.decide(self.recruiter, 'rejected')

    def test_stale_decision_is_rejected(self):
        from services.recruitment_decisions import DecisionConflict

        self.decide(self.recruiter)
        with self.assertRaises(DecisionConflict):
            change_application_status(application_id=self.application.pk, actor=self.recruiter,
                                      target='rejected', reason='Reviewed', expected_version=0)
        self.assertEqual(self.application.decision_events.count(), 1)

    def test_api_stale_version_returns_conflict(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.jobs.views import JobApplicationViewSet

        self.decide(self.recruiter)
        request = APIRequestFactory().patch('/', {
            'status': 'rejected', 'reason': 'Reviewed', 'expected_version': 0,
        }, format='json')
        force_authenticate(request, user=self.recruiter)
        response = JobApplicationViewSet.as_view({'patch': 'update_status'})(request, pk=self.application.pk)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.application.decision_events.count(), 1)

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(ValidationError):
            change_application_status(application_id=self.application.pk, actor=self.recruiter,
                                      target='shortlisted', expected_version=True)
        self.assertFalse(self.application.decision_events.exists())

    def test_acceptance_then_reopening(self):
        self.decide(self.recruiter)
        change_application_status(application_id=self.application.pk, actor=self.recruiter,
                                  target='accepted', reason='Committee approval', expected_version=1)
        change_application_status(application_id=self.application.pk, actor=self.recruiter,
                                  target='pending', reason='Candidate requested review', expected_version=2)
        self.application.refresh_from_db()
        self.assertEqual(self.application.decision_version, 3)
        self.assertEqual(self.application.status, 'pending')
        self.assertEqual(self.application.decision_events.count(), 3)

    def test_options_expose_only_valid_transitions(self):
        response = self.api(self.recruiter, 'decision_options', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['version'], 0)
        self.assertEqual(response.data['allowed_statuses'], ['shortlisted', 'rejected'])
        self.assertEqual(self.api(self.candidate, 'decision_options', 'get').status_code, 403)

    def test_history_restricted_to_recruiter(self):
        self.decide(self.recruiter)
        self.assertEqual(self.api(self.candidate, 'decision_history', 'get').status_code, 403)
        self.assertEqual(self.api(self.outsider, 'decision_history', 'get').status_code, 404)
        response = self.api(self.recruiter, 'decision_history', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_audited_application_cannot_be_deleted(self):
        self.decide(self.recruiter)
        self.assertEqual(self.api(self.recruiter, 'destroy', 'delete').status_code, 409)
        self.assertTrue(JobApplication.objects.filter(pk=self.application.pk).exists())
        self.assertEqual(self.application.decision_events.count(), 1)

    def test_candidate_cannot_delete_application(self):
        self.assertEqual(self.api(self.candidate, 'destroy', 'delete').status_code, 403)

    def api(self, actor, action, method):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.jobs.views import JobApplicationViewSet

        request = getattr(APIRequestFactory(), method)('/')
        force_authenticate(request, user=actor)
        return JobApplicationViewSet.as_view({method: action})(request, pk=self.application.pk)

    def decide(self, actor, target='shortlisted'):
        return change_application_status(
            application_id=self.application.pk, actor=actor, target=target,
        )
