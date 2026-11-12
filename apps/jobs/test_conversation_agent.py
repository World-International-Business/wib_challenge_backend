from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.jobs.models import JobCategory, JobOffer, OfferConversation
from apps.organizations.models import Organization
from services.offer_agent import AgentReply, JobCard


def _card(**over):
    data = dict(
        title='Développeur Django', poste='Développement Web', description='desc',
        responsibilities='resp', requirements='req', benefits='ben',
        skills=['Django'], job_type='cdi', experience_level='senior',
        location='Douala', remote_allowed=True, salary='1M XAF', currency='XAF',
        application_instructions='postuler ici', required_documents=['cv'],
        expires_at='2026-12-12')
    return JobCard(**{**data, **over})


def _reply(**over):
    data = dict(reply='Voici la fiche.', questions=[], quick_replies=['Oui'],
                job_card=_card(), ready_to_publish=True)
    return AgentReply(**{**data, **over})


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OfferConversationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(email='conv@example.test', password='test')
        Organization.objects.create(account=cls.user, name='Org')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.provider = Mock()
        self.provider.models.generate_content.return_value = SimpleNamespace(parsed=_reply())
        patcher = patch('services.offer_agent.get_genai_client', return_value=self.provider)
        self.mock_client = patcher.start()
        self.addCleanup(patcher.stop)

    def _conv_with_reply(self, reply):
        self.provider.models.generate_content.return_value = SimpleNamespace(parsed=reply)
        return self.client.post('/api/jobs/offer-conversations/', {'content': 'besoin dev django'}, format='json')

    def test_create_with_message_returns_blocks_and_review_state(self):
        response = self._conv_with_reply(_reply())
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.json()['state'], 'review')
        assistant = response.json()['messages'][1]
        types = [b['type'] for b in assistant['blocks']]
        self.assertIn('text', types)
        self.assertIn('job_card', types)
        self.assertIn('quick_replies', types)
        card = next(b['data'] for b in assistant['blocks'] if b['type'] == 'job_card')
        self.assertEqual(card['poste'], JobCategory.objects.get(title='Développement Web').pk)
        self.assertTrue(all(card[k] not in (None, '', []) for k in card))

    def test_clarifying_questions_set_state_and_quick_replies(self):
        response = self._conv_with_reply(_reply(reply='Précisez le salaire ?', questions=['salaire ?'], job_card=None))
        self.assertEqual(response.json()['state'], 'clarifying')
        assistant = response.json()['messages'][1]
        self.assertNotIn('job_card', [b['type'] for b in assistant['blocks']])

    def test_message_roundtrip_and_throttle_free_listing(self):
        conv_id = self._conv_with_reply(_reply(questions=['?'], job_card=None, ready_to_publish=False)).json()['id']
        response = self.client.post(f'/api/jobs/offer-conversations/{conv_id}/messages/', {'content': 'CDI à Douala'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.json()['message']['role'], 'assistant')
        listing = self.client.get('/api/jobs/offer-conversations/')
        body = listing.json()
        self.assertEqual(len(body['results'] if isinstance(body, dict) else body), 1)

    def test_edit_user_message_truncates_and_regenerates(self):
        conv_id = self._conv_with_reply(_reply(questions=['?'], job_card=None)).json()['id']
        first = self.client.get(f'/api/jobs/offer-conversations/{conv_id}/').json()['messages'][0]
        self.client.post(f'/api/jobs/offer-conversations/{conv_id}/messages/', {'content': 'second'}, format='json')
        self.assertEqual(self.client.get(f'/api/jobs/offer-conversations/{conv_id}/').json()['messages'].__len__(), 4)
        response = self.client.patch(f'/api/jobs/offer-conversations/{conv_id}/messages/{first["id"]}/', {'content': 'edited need'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        messages = self.client.get(f'/api/jobs/offer-conversations/{conv_id}/').json()['messages']
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['content'], 'edited need')

    def test_approve_creates_and_publishes_offer_with_channels(self):
        conv_id = self._conv_with_reply(_reply()).json()['id']
        response = self.client.post(f'/api/jobs/offer-conversations/{conv_id}/approve/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        data = response.json()
        self.assertEqual(data['status'], 'published')
        offer = JobOffer.objects.get(pk=data['offerId'])
        self.assertEqual(offer.status, 'published')
        self.assertEqual(offer.poste.title, 'Développement Web')
        self.assertEqual(offer.job_type, 'cdi')
        states = {c['name']: c['state'] for c in data['channels']}
        self.assertEqual(states['site_carriere'], 'published')
        self.assertEqual(OfferConversation.objects.get(pk=conv_id).state, 'published')

    def test_approve_without_draft_is_conflict(self):
        conversation = OfferConversation.objects.create(organization=self.user.organization, user=self.user)
        response = self.client.post(f'/api/jobs/offer-conversations/{conversation.pk}/approve/', {}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'draft_missing')

    def test_conversation_is_scoped_to_organization(self):
        other = get_user_model().objects.create_user(email='other@example.test', password='test')
        Organization.objects.create(account=other, name='OtherOrg')
        conv_id = self._conv_with_reply(_reply()).json()['id']
        self.client.force_authenticate(user=other)
        body = self.client.get('/api/jobs/offer-conversations/').json()
        self.assertEqual(body['results'] if isinstance(body, dict) else body, [])
        self.assertEqual(self.client.get(f'/api/jobs/offer-conversations/{conv_id}/').status_code, 404)

    def test_anonymous_cannot_use_conversations(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get('/api/jobs/offer-conversations/').status_code, [401, 403])
        self.mock_client.assert_not_called()

    def test_failed_agent_leaves_no_dangling_user_message(self):
        from services.offer_agent import OfferAgentError
        conv_id = self._conv_with_reply(_reply()).json()['id']
        with patch('apps.jobs.conversation_api.run_offer_agent', side_effect=OfferAgentError('ai_rate_limited', 'x', 429)):
            response = self.client.post(f'/api/jobs/offer-conversations/{conv_id}/messages/', {'content': 'retry me'}, format='json')
        self.assertEqual(response.status_code, 429)
        messages = self.client.get(f'/api/jobs/offer-conversations/{conv_id}/').json()['messages']
        self.assertEqual([m['role'] for m in messages], ['user', 'assistant'])

    def test_publish_returns_channel_states(self):
        offer = JobOffer.objects.create(
            title='x', company=self.user.organization, poste=JobCategory.objects.create(title='Cat'),
            description='d', requirements='r', job_type='cdi', experience_level='junior', location='Douala')
        response = self.client.post(f'/api/jobs/offers/{offer.pk}/publish/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'published')
        states = {c['name']: c['state'] for c in data['channels']}
        self.assertEqual(states['site_carriere'], 'published')
        self.assertIn('offer', data)

    def test_distribute_filters_channels(self):
        offer = JobOffer.objects.create(
            title='x', company=self.user.organization, poste=JobCategory.objects.create(title='Cat'),
            description='d', requirements='r', job_type='cdi', experience_level='junior', location='Douala')
        response = self.client.post(f'/api/jobs/offers/{offer.pk}/distribute/', {'channels': ['emploi_cm', 'nope']}, format='json')
        names = {c['name'] for c in response.json()['channels']}
        self.assertEqual(names, {'emploi_cm', 'nope'})
