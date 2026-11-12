from types import SimpleNamespace
from unittest.mock import Mock, patch

from decouple import UndefinedValueError
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from google.genai.errors import ClientError, ServerError
from httpx import ReadTimeout
from rest_framework.test import APIClient

from apps.core.models import Technology
from apps.jobs.models import JobOffer
from apps.organizations.models import Organization
from services.generate_offer import OfferInfo


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OfferGenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(email='offers@example.test', password='test')
        Organization.objects.create(account=cls.user, name='Company')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.provider = Mock()
        self.provider.models.generate_content.return_value = SimpleNamespace(
            parsed=OfferInfo(title='Développeur Django', description='Développer des applications',
                responsibilities='Développer et tester', requirements='Django', benefits='Formation',
                analyze='Préciser le salaire', skills=['Django']),
        )
        patcher = patch('services.generate_offer.get_genai_client', return_value=self.provider)
        self.mock_client = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, **data):
        return self.client.post('/api/jobs/offers/generate/', {'prompt': 'Recruter un développeur Django', **data}, format='json')

    @override_settings(GEMINI_OFFER_MODEL='configured-offer-model')
    def test_generation_uses_configured_model_without_creating_records(self):
        response = self.post(skills=['Django'])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.json()['skills'], ['Django'])
        self.assertEqual(self.provider.models.generate_content.call_args.kwargs['model'], 'configured-offer-model')
        self.assertIn('Django', self.provider.models.generate_content.call_args.kwargs['contents'][0])
        self.assertEqual(Technology.objects.count(), 0)
        self.assertEqual(JobOffer.objects.count(), 0)

    def test_retired_model_returns_explicit_safe_error(self):
        self.provider.models.generate_content.side_effect = ClientError(404, {'error': {'message': 'private provider URL or key', 'status': 'NOT_FOUND'}})
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'ai_model_unavailable')
        self.assertNotIn('private', str(response.data))

    def test_quota_error_is_not_an_internal_server_error(self):
        self.provider.models.generate_content.side_effect = ClientError(429, {'error': {'message': 'private quota details', 'status': 'RESOURCE_EXHAUSTED'}})
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['code'], 'ai_rate_limited')
        self.assertNotIn('private', str(response.data))

    def test_provider_outage_is_reported_as_unavailable(self):
        self.provider.models.generate_content.side_effect = ServerError(503, {'error': {'message': 'private error'}})
        self.assertEqual(self.post().status_code, 503)

    def test_timeout_is_reported_as_gateway_timeout(self):
        self.provider.models.generate_content.side_effect = ReadTimeout('private request URL')
        response = self.post()
        self.assertEqual(response.status_code, 504)
        self.assertNotIn('private', str(response.data))

    def test_missing_configuration_returns_safe_error(self):
        self.mock_client.side_effect = UndefinedValueError('GENAI_API_KEY not found with private path')
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'ai_not_configured')
        self.assertNotIn('private', str(response.data))

    def test_unparseable_response_returns_bad_gateway(self):
        self.provider.models.generate_content.return_value = SimpleNamespace(parsed=None, text='not JSON private content')
        response = self.post()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['code'], 'ai_invalid_response')
        self.assertNotIn('private', str(response.data))

    def test_json_text_fallback_and_nullable_fields(self):
        self.provider.models.generate_content.return_value = SimpleNamespace(parsed=None, text='{"title":"Django","description":null,"skills":null}')
        response = self.post()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.json()['title'], 'Django')
        self.assertEqual(response.json()['description'], '')
        self.assertEqual(response.json()['skills'], [])

    def test_empty_response_is_not_reported_as_generated_offer(self):
        self.provider.models.generate_content.return_value = SimpleNamespace(parsed=OfferInfo())
        self.assertEqual(self.post().status_code, 502)

    def test_invalid_input_does_not_call_provider_or_create_tags(self):
        response = self.post(prompt='', skills=['Django'])
        self.assertEqual(response.status_code, 400)
        self.mock_client.assert_not_called()
        self.assertEqual(Technology.objects.count(), 0)

    def test_invalid_api_key_is_reported_as_authentication_failure(self):
        self.provider.models.generate_content.side_effect = ClientError(400, {'error': {'message': 'API key not valid. private key', 'status': 'INVALID_ARGUMENT', 'details': [{'reason': 'API_KEY_INVALID'}]}})
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'ai_authentication_failed')
        self.assertNotIn('private', str(response.data))

    def test_provider_authentication_error_is_not_exposed(self):
        self.provider.models.generate_content.side_effect = ClientError(403, {'error': {'message': 'private key rejected'}})
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'ai_authentication_failed')
        self.assertNotIn('private', str(response.data))

    def test_parsed_dictionary_is_supported(self):
        self.provider.models.generate_content.return_value = SimpleNamespace(parsed={'title': 'Django', 'skills': ['Python']})
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['skills'], ['Python'])

    def test_invalid_generated_fields_are_bad_gateway_not_bad_input(self):
        self.provider.models.generate_content.return_value = SimpleNamespace(parsed=OfferInfo(title='x' * 256))
        response = self.post()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['code'], 'ai_invalid_response')

    def test_unexpected_error_does_not_leak_in_response_or_logs(self):
        self.provider.models.generate_content.side_effect = RuntimeError('private credential or prompt')
        with patch('apps.jobs.views.logger') as logger:
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private', str(response.data))
        self.assertNotIn('private', str(logger.error.call_args))

    def test_anonymous_generation_is_rejected(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.post().status_code, [401, 403])
        self.mock_client.assert_not_called()
