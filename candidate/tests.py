from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from core.models import Profession, Technology


class CandidateProfileTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='localhost@user.com',
            password='password',
            first_name='John',
        )
        self.fullstack = Profession.objects.create(title='Fullstack Developer')
        self.javascript = Technology.objects.create(name='JavaScript')
        self.python = Technology.objects.create(name='Python')
        self.client.force_authenticate(user=self.user)

    def test_create_candidate_profile(self):
        response = self.client.post(reverse('candidates:candidates-list'), {
            'profession': self.fullstack.title,
            'technologies': [
                {'name': self.javascript.name, 'level': 2},
                {'name': self.python.name, 'level': 3},
            ]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['profession'], self.fullstack.title)
        self.assertTrue(response.data['user'].endswith(reverse('accounts:users-detail', args=[self.user.pk])))
        self.assertEqual(response.data['technologies'][0]['name'], 'JavaScript')
        self.assertEqual(response.data['technologies'][0]['level'], 2)
        self.assertEqual(response.data['technologies'][1]['name'], 'Python')
        self.assertEqual(response.data['technologies'][1]['level'], 3)

    def test_update_profile_reset_technologies_list(self):
        response = self.client.post(reverse('candidates:candidates-list'), {
            'profession': self.fullstack.title,
            'technologies': [
                {'name': self.javascript.name, 'level': 2},
                {'name': self.python.name, 'level': 3},
            ]
        }, format='json')
        candidate_id = response.data['id']

        response = self.client.patch(reverse('candidates:candidates-detail', args=[candidate_id]), {
            'profession': self.fullstack.title,
            'technologies': [
                {'name': self.python.name, 'level': 2},
                {'name': self.javascript.name, 'level': 1},
            ]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['technologies'][0]['name'], 'Python')
        self.assertEqual(response.data['technologies'][0]['level'], 2)
        self.assertEqual(response.data['technologies'][1]['name'], 'JavaScript')
        self.assertEqual(response.data['technologies'][1]['level'], 1)
