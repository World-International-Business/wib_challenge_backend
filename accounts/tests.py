import random
import string

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from accounts.models import User


class AccountTestCase(APITestCase):

    def create_random_user(self, create=True, **kwargs):
        email = f'{"".join(random.choices(string.ascii_letters, k=10))}@gmail.com'
        defaults = {
            'first_name': "John",
            'last_name': "Doe",
            **kwargs
        }
        if create:
            return User.objects.create_user(email=email, password='password123', **defaults)
        return {**defaults, 'email': email, 'password': 'password123'}

    def setUp(self):
        self.user = self.create_random_user()
        self.admin = self.create_random_user(role=User.Roles.ADMIN, is_staff=True)

    def test_register(self):
        data = self.create_random_user(create=False)
        response = self.client.post(reverse('accounts:register'), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, 'Register must return 200 status code')
        self.assertIn('access', response.data, 'Response must contain access token')
        self.assertIn('refresh', response.data, 'Response must contain refresh token')
        self.assertIn('data', response.data, 'Response must contain user data')
        self.assertEqual(response.data['data']['email'], data['email'], 'User email must match')
        self.assertEqual(response.data['data']['first_name'], data['first_name'], 'User first name must match')
        self.assertEqual(response.data['data']['last_name'], data['last_name'], 'User last name must match')

    def test_login(self):
        response = self.client.post(reverse('accounts:token_obtain_pair'),
                                    data={'email': self.user.email, 'password': 'password123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Login must return 200 status code')
        self.assertIn('access', response.data, 'Response must contain access token')
        self.assertIn('refresh', response.data, 'Response must contain refresh token')
        self.assertIn('data', response.data, 'Response must contain user data')
        self.assertEqual(response.data['data']['email'], self.user.email, 'User email must match')
        self.assertEqual(response.data['data']['first_name'], self.user.first_name, 'User first name must match')
        self.assertEqual(response.data['data']['last_name'], self.user.last_name, 'User last name must match')

    def test_logout_blacklist_token(self):
        response = self.client.post(reverse('accounts:token_obtain_pair'),
                                    data={'email': self.user.email, 'password': 'password123'})

        refresh_token = response.data['refresh']
        access_token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post(reverse('accounts:logout'), data={'refresh': refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Logout must return 200 status code')

        response = self.client.post(reverse('accounts:token_refresh'), data={'refresh': refresh_token})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, 'Token must be invalid after logout')

    def test_forgot_password(self):
        response = self.client.post(reverse('accounts:password_reset'), data={'email': self.user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Forgot password must return 200 status code')
        self.assertIn('detail', response.data, 'Response must contain detail message')
        self.assertIn('uidb64', response.data, 'Response must contain uidb64')
        self.assertIn('token', response.data, 'Response must contain token')
        self.assertIn('verification_code', response.data, 'Response must contain verification code')

        response = self.client.post(reverse('accounts:password_reset_confirm', kwargs={
            'uidb64': response.data['uidb64'],
            'token': response.data['token']
        }), data={'password': 'password1234', 'verification_code': response.data['verification_code']})
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Reset password must return 200 status code')
        self.assertIn('message', response.data, 'Response must contain message')

    def test_list_users(self):
        response = self.client.get(reverse('accounts:users-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'List users must return 200 status code')
        self.assertIn('count', response.data, 'Response must contain count')
        self.assertIn('results', response.data, 'Response must contain results')
        self.assertEqual(len(response.data['results']), 1, 'Response must contain 1 user with admins')

        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse('accounts:users-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'List users must return 200 status code')
        self.assertIn('count', response.data, 'Response must contain count')
        self.assertIn('results', response.data, 'Response must contain results')
        self.assertEqual(len(response.data['results']), 2, 'Response must contain 2 users with admins')

    def test_retrieve_user(self):
        response = self.client.get(reverse('accounts:users-detail', kwargs={'pk': self.user.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Retrieve user must return 200 status code')
        self.assertIn('email', response.data, 'Response must contain email')
        self.assertIn('first_name', response.data, 'Response must contain first name')
        self.assertIn('last_name', response.data, 'Response must contain last name')

        response = self.client.get(reverse('accounts:users-detail', kwargs={'pk': self.admin.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND,
                         'Retrieve admin must return 404 status code for not admin user')

    def test_update_user(self):
        data = {'first_name': 'Jane'}
        dummy_user = self.create_random_user()
        response = self.client.patch(reverse('accounts:users-detail', kwargs={'pk': dummy_user.pk}), data=data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED,
                         'Update user must return 401 status for unauthenticated user')

        self.client.force_authenticate(user=self.user)
        response = self.client.patch(reverse('accounts:users-detail', kwargs={'pk': dummy_user.pk}), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN,
                         'Update user must return 403 status code for not self user and not admin')

        response = self.client.patch(reverse('accounts:users-detail', kwargs={'pk': self.user.pk}), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK,
                         'Update user must return 200 status code for self user')
        self.assertEqual(response.data['first_name'], data['first_name'], 'User first name must match')

        self.client.force_authenticate(user=self.admin)
        data = {'first_name': 'Johnny'}

        response = self.client.patch(reverse('accounts:users-detail', kwargs={'pk': self.user.pk}), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Update user must return 200 status code for admin')
        self.assertEqual(response.data['first_name'], data['first_name'], 'User first name must match')

    def test_delete_user(self):
        dummy_user = self.create_random_user()
        response = self.client.delete(reverse('accounts:users-detail', kwargs={'pk': dummy_user.pk}))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED,
                         'Delete user must return 401 status for unauthenticated user')

        self.client.force_authenticate(user=self.user)
        response = self.client.delete(reverse('accounts:users-detail', kwargs={'pk': dummy_user.pk}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN,
                         'Delete user must return 403 status code for not self user and not admin')

        response = self.client.delete(reverse('accounts:users-detail', kwargs={'pk': self.user.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT,
                         'Delete user must return 204 status code for self user')
        self.assertFalse(User.objects.filter(pk=self.user.pk, is_active=True).exists(), 'User must be deleted')

        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(reverse('accounts:users-detail', kwargs={'pk': dummy_user.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT,
                         'Delete user must return 204 status code for admin')
        self.assertFalse(User.objects.filter(pk=dummy_user.pk, is_active=True).exists(), 'User must be deleted')

    def test_password_change(self):
        data = {'old_password': 'password1243', 'new_password': 'password456'}
        change_password_url = reverse('accounts:users-change-password', kwargs={'pk': self.user.pk})

        response = self.client.post(change_password_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED,
                         'Change password must return 401 status for unauthenticated user')

        self.client.force_authenticate(user=self.user)

        response = self.client.post(change_password_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST,
                         'Change password must return 400 status code for incorrect old password')

        data['old_password'] = 'password123'

        response = self.client.post(change_password_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Change password must return 200 status code')
        self.assertIn('message', response.data, 'Response must contain message')

        self.client.force_authenticate(user=self.admin)

        self.client.post(change_password_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK,
                         'Change password must return 200 status code for admin')
        self.assertIn('message', response.data, 'Response must contain message')
