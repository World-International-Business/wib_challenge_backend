"""Tests des credentials de canaux de diffusion par organisation."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.jobs.models import JobCategory, JobOffer
from apps.organizations.models import Organization, OrganizationChannelCredential as Cred
from services import linkedin_oauth
from services.offer_distribution import distribute_offer

User = get_user_model()


def make_org(email='org-channels@wib.dev'):
    user = User.objects.create_user(email=email, password='pass123456')
    return Organization.objects.create(name='Org Channels', account=user), user


def make_offer(org):
    cat, _ = JobCategory.objects.get_or_create(title='QA', defaults={'slug': 'qa-channels'})
    return JobOffer.objects.create(
        company=org, poste=cat, title='Dev QA', description='desc', requirements='req',
        job_type='cdi', experience_level='senior', location='Douala', status='published')


class ChannelStatusTests(TestCase):
    def setUp(self):
        self.org, self.user = make_org()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_channels_status_no_secret(self):
        self.client.post(f'/api/organizations/{self.org.pk}/channels/emploi_cm/connect/',
                         {'apiKey': 'super-secret-key'}, format='json')
        r = self.client.get(f'/api/organizations/{self.org.pk}/channels/')
        self.assertEqual(r.status_code, 200)
        body = str(r.json())
        self.assertNotIn('super-secret-key', body)
        emploi = next(ch for ch in r.json()['channels'] if ch['name'] == 'emploi_cm')
        self.assertEqual(emploi['status'], 'pending')  # pas de base URL -> pending

    def test_cross_org_isolation(self):
        other, other_user = make_org('other-channels@wib.dev')
        other_client = APIClient()
        other_client.force_authenticate(other_user)
        self.assertEqual(other_client.get(f'/api/organizations/{self.org.pk}/channels/').status_code, 404)
        self.assertEqual(
            other_client.delete(f'/api/organizations/{self.org.pk}/channels/emploi_cm/').status_code, 404)

    def test_emploi_cm_requires_key_and_disconnect(self):
        r = self.client.post(f'/api/organizations/{self.org.pk}/channels/emploi_cm/connect/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.client.post(f'/api/organizations/{self.org.pk}/channels/emploi_cm/connect/',
                         {'apiKey': 'k'}, format='json')
        self.assertEqual(self.client.delete(f'/api/organizations/{self.org.pk}/channels/emploi_cm/').status_code, 204)
        self.assertEqual(self.client.delete(f'/api/organizations/{self.org.pk}/channels/emploi_cm/').status_code, 404)


class LinkedInOAuthTests(TestCase):
    def setUp(self):
        self.org, self.user = make_org('linkedin-org@wib.dev')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_connect_returns_auth_url(self):
        with patch.dict('os.environ', {'LINKEDIN_CLIENT_ID': 'cli', 'LINKEDIN_CLIENT_SECRET': 'sec'}):
            r = self.client.get(f'/api/organizations/{self.org.pk}/linkedin/connect/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('linkedin.com/oauth/v2/authorization', r.json()['authUrl'])
        self.assertIn('state=', r.json()['authUrl'])

    def test_callback_rejects_bad_state(self):
        r = APIClient().get(f'/api/organizations/{self.org.pk}/linkedin/callback/?code=x&state=bad')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['connected'])

    def test_callback_rejects_org_mismatch(self):
        state = linkedin_oauth.build_state(999999, self.user.pk)
        r = APIClient().get(f'/api/organizations/{self.org.pk}/linkedin/callback/?code=x&state={state}')
        self.assertEqual(r.status_code, 400)

    def test_callback_stores_encrypted_credential(self):
        state = linkedin_oauth.build_state(self.org.pk, self.user.pk)
        with patch('services.linkedin_oauth.exchange_code',
                   return_value={'access_token': 'tok_abc', 'expires_in': 3600}), \
             patch('services.linkedin_oauth.resolve_organization_urn', return_value='urn:li:organization:7'):
            r = APIClient().get(f'/api/organizations/{self.org.pk}/linkedin/callback/?code=c&state={state}')
        self.assertEqual(r.status_code, 200)
        cred = Cred.objects.get(organization=self.org, channel='linkedin')
        self.assertEqual(cred.status, 'connected')
        self.assertNotEqual(cred.secret, 'tok_abc')  # chiffré en base
        self.assertEqual(cred.get_secret(), 'tok_abc')


class DistributionWithCredentialsTests(TestCase):
    def setUp(self):
        self.org, self.user = make_org('dist-org@wib.dev')
        self.org.preferred_channels = ['linkedin', 'emploi_cm']
        self.org.linkedin_page_url = 'https://www.linkedin.com/company/acme'
        self.org.emploi_cm_account = 'acc-1'
        self.org.save()
        self.offer = make_offer(self.org)

    def test_fails_clean_without_credentials(self):
        results = {c['name']: c for c in distribute_offer(self.offer)}
        self.assertEqual(results['site_carriere']['state'], 'published')
        self.assertEqual(results['linkedin']['state'], 'failed')
        self.assertIn('non connecté', results['linkedin']['error'])
        self.assertEqual(results['emploi_cm']['state'], 'failed')

    def test_linkedin_publish_with_org_token(self):
        cred = Cred.objects.create(organization=self.org, channel='linkedin',
                                   external_id='urn:li:organization:7', status='connected')
        cred.set_secret('org-token')
        cred.save()
        fake = MagicMock(status_code=201, headers={'x-restli-id': 'urn:li:share:9'})
        with patch('services.linkedin_oauth.requests.post', return_value=fake):
            results = {c['name']: c for c in distribute_offer(self.offer, channels=['linkedin'])}
        self.assertEqual(results['linkedin']['state'], 'published')
        self.assertIn('urn:li:share:9', results['linkedin']['url'])

    def test_expired_credential_fails_and_notifies(self):
        cred = Cred.objects.create(organization=self.org, channel='linkedin',
                                   external_id='urn:li:organization:7', status='expired')
        results = {c['name']: c for c in distribute_offer(self.offer, channels=['linkedin'])}
        self.assertEqual(results['linkedin']['state'], 'failed')
        self.assertIn('non connecté', results['linkedin']['error'])
