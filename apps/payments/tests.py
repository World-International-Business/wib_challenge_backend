import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.learning.models import Course, CourseEnrollment
from apps.payments.models import Payment


class PaymentSecurityTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='candidate@example.com', password='test-password')
        self.course = Course.objects.create(
            title='Paiement test', description='Formation', level='beginner', is_published=True,
            is_free=False, price=5000, currency='XOF', certificate_enabled=False,
        )
        self.payload = {
            'cpm_trans_id': 'abc123',
            'cpm_error_code': '00',
            'cpm_amount': '5000',
        }
        self.body = json.dumps(self.payload, separators=(',', ':')).encode('utf-8')
        self.secret = 'test-secret'
        self.signature = hmac.new(self.secret.encode('utf-8'), self.body, hashlib.sha256).hexdigest()

    @override_settings(CINETPAY_API_KEY='key', CINETPAY_SITE_ID='site')
    def test_paid_course_checkout_creates_payment(self):
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/payments/course-checkout/', {
            'course_id': self.course.id,
            'provider': 'cinetpay',
            'return_url': 'https://example.com/success',
            'cancel_url': 'https://example.com/cancel',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Payment.objects.filter(user=self.user, course=self.course).exists())

    @override_settings(CINETPAY_API_KEY='key', CINETPAY_SITE_ID='site')
    def test_frontend_payment_confirmation_rejected(self):
        """Le paiement n'est jamais validé par un appel front-end"""
        self.client.force_authenticate(self.user)
        self.client.post('/api/payments/course-checkout/', {
            'course_id': self.course.id,
            'provider': 'cinetpay',
            'return_url': 'https://example.com/success',
            'cancel_url': 'https://example.com/cancel',
        })
        payment = Payment.objects.get()
        self.assertNotEqual(payment.status, Payment.Status.SUCCEEDED)

    @override_settings(CINETPAY_SECRET_KEY='test-secret')
    def test_webhook_enrollment_activation(self):
        payment = Payment.objects.create(
            user=self.user,
            purpose=Payment.Purpose.COURSE_ENROLLMENT,
            course=self.course,
            amount=self.course.price,
            currency=self.course.currency,
            provider='cinetpay',
            provider_reference='abc123',
        )
        response = self.client.post('/api/payments/webhooks/cinetpay/', self.body,
                                    content_type='application/json', HTTP_X_SIGNATURE=self.signature)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertTrue(CourseEnrollment.objects.filter(user=self.user, course=self.course).exists())

    @override_settings(CINETPAY_SECRET_KEY='test-secret')
    def test_duplicate_webhook_is_idempotent(self):
        Payment.objects.create(
            user=self.user,
            purpose=Payment.Purpose.COURSE_ENROLLMENT,
            course=self.course,
            amount=self.course.price,
            currency=self.course.currency,
            provider='cinetpay',
            provider_reference='abc123',
            status=Payment.Status.SUCCEEDED,
        )
        response = self.client.post('/api/payments/webhooks/cinetpay/', self.body,
                                    content_type='application/json', HTTP_X_SIGNATURE=self.signature)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'IDEMPOTENT')

    @override_settings(CINETPAY_SECRET_KEY='test-secret')
    def test_invalid_webhook_signature_rejected(self):
        Payment.objects.create(
            user=self.user,
            purpose=Payment.Purpose.COURSE_ENROLLMENT,
            course=self.course,
            amount=self.course.price,
            currency=self.course.currency,
            provider='cinetpay',
            provider_reference='abc123',
        )
        response = self.client.post('/api/payments/webhooks/cinetpay/', self.body,
                                    content_type='application/json', HTTP_X_SIGNATURE='bad-signature')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
