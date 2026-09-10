import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.learning.models import Course, CourseEnrollment
from .models import Payment
from .providers import PaymentProviderError, get_provider
from .serializers import CourseCheckoutSerializer, PaymentSerializer

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['webhooks']:
            return [permissions.AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Payment.objects.none()
        return Payment.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='course-checkout')
    def course_checkout(self, request):
        serializer = CourseCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = get_object_or_404(Course, id=serializer.validated_data['course_id'])

        if course.is_free or (course.price or 0) == 0:
            return Response(
                {'code': 'PAYMENT_NOT_REQUIRED', 'detail': 'La formation est gratuite.', 'fieldErrors': {}, 'metadata': {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if CourseEnrollment.objects.filter(user=request.user, course=course, status=CourseEnrollment.Status.ACTIVE).exists():
            return Response(
                {'code': 'ENROLLMENT_ALREADY_ACTIVE', 'detail': 'Vous êtes déjà inscrit.', 'fieldErrors': {}, 'metadata': {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider = get_provider(serializer.validated_data['provider'])
        except PaymentProviderError as e:
            return Response(
                {'code': 'PAYMENT_PROVIDER_ERROR', 'detail': str(e), 'fieldErrors': {}, 'metadata': {}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        with transaction.atomic():
            payment = Payment.objects.create(
                user=request.user,
                purpose=Payment.Purpose.COURSE_ENROLLMENT,
                course=course,
                amount=course.price,
                currency=course.currency,
                provider=serializer.validated_data['provider'],
                metadata={
                    'return_url': serializer.validated_data['return_url'],
                    'cancel_url': serializer.validated_data['cancel_url'],
                },
            )
            try:
                checkout = provider.create_checkout(
                    payment,
                    serializer.validated_data['return_url'],
                    serializer.validated_data['cancel_url'],
                )
            except PaymentProviderError as e:
                payment.status = Payment.Status.FAILED
                payment.failure_reason = str(e)
                payment.save(update_fields=['status', 'failure_reason', 'updated_at'])
                return Response(
                    {'code': 'PAYMENT_FAILED', 'detail': str(e), 'fieldErrors': {}, 'metadata': {}},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            payment.provider_reference = checkout['provider_reference']
            payment.checkout_url = checkout['checkout_url']
            payment.metadata.update(checkout.get('metadata', {}))
            payment.save(update_fields=['provider_reference', 'checkout_url', 'metadata', 'updated_at'])

        return Response({
            'payment_id': payment.id,
            'status': payment.status,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'checkout_url': payment.checkout_url,
            'provider_reference': payment.provider_reference,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path=r'webhooks/(?P<provider>[^/.]+)', permission_classes=[permissions.AllowAny])
    def webhooks(self, request, provider=None):
        try:
            provider_instance = get_provider(provider)
        except PaymentProviderError as e:
            return Response({'code': 'UNKNOWN_PROVIDER', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(request.body.decode('utf-8')) if request.body else request.data
        except json.JSONDecodeError:
            return Response({'code': 'INVALID_PAYLOAD', 'detail': 'Payload JSON invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        signature = request.headers.get('X-Signature') or request.headers.get('Stripe-Signature') or ''
        secret = ''
        if provider == 'cinetpay':
            secret = getattr(settings, 'CINETPAY_SECRET_KEY', '')
        elif provider == 'stripe':
            secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        elif provider == 'paypal':
            secret = getattr(settings, 'PAYPAL_WEBHOOK_ID', '')

        if not provider_instance.verify_webhook(request.body, signature, secret):
            logger.warning('Webhook signature invalide pour %s', provider)
            return Response({'code': 'INVALID_SIGNATURE', 'detail': 'Signature invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        parsed = provider_instance.parse_webhook(payload)
        provider_reference = parsed.get('provider_reference')
        if not provider_reference:
            return Response({'code': 'MISSING_REFERENCE', 'detail': 'Référence manquante.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(provider_reference=provider_reference, provider=provider)
        except Payment.DoesNotExist:
            return Response({'code': 'PAYMENT_NOT_FOUND', 'detail': 'Paiement introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        if payment.status in [Payment.Status.SUCCEEDED, Payment.Status.REFUNDED]:
            return Response({'code': 'IDEMPOTENT', 'detail': 'Paiement déjà confirmé.'}, status=status.HTTP_200_OK)

        with transaction.atomic():
            payment.webhook_payload = payload
            payment.webhook_signature = signature[:500]
            new_status = parsed.get('status')
            if new_status == 'succeeded':
                payment.status = Payment.Status.SUCCEEDED
                payment.paid_at = timezone.now()
                if payment.purpose == Payment.Purpose.COURSE_ENROLLMENT and payment.course:
                    CourseEnrollment.objects.get_or_create(
                        user=payment.user,
                        course=payment.course,
                        defaults={
                            'status': CourseEnrollment.Status.ACTIVE,
                            'source': CourseEnrollment.Source.SELF,
                            'payment': payment,
                        },
                    )
            elif new_status == 'failed':
                payment.status = Payment.Status.FAILED
                payment.failure_reason = str(parsed.get('metadata', {}))[:250]
            elif new_status == 'cancelled':
                payment.status = Payment.Status.CANCELLED
            else:
                payment.status = Payment.Status.PROCESSING
            payment.save(update_fields=['status', 'paid_at', 'failure_reason', 'webhook_payload', 'webhook_signature', 'updated_at'])

        return Response({'payment_id': payment.id, 'status': payment.status}, status=status.HTTP_200_OK)
