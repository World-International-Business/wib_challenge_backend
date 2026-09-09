import hashlib
import hmac
import secrets
import uuid

from django.conf import settings


class PaymentProviderError(Exception):
    pass


class PaymentProvider:
    def create_checkout(self, payment, return_url, cancel_url):
        raise NotImplementedError

    def verify_webhook(self, request_body, signature, secret):
        raise NotImplementedError

    def parse_webhook(self, payload):
        raise NotImplementedError


class CinetPayProvider(PaymentProvider):
    def create_checkout(self, payment, return_url, cancel_url):
        api_key = getattr(settings, 'CINETPAY_API_KEY', '')
        site_id = getattr(settings, 'CINETPAY_SITE_ID', '')
        if not api_key or not site_id:
            raise PaymentProviderError('CinetPay non configuré')
        reference = secrets.token_urlsafe(24)
        return {
            'provider_reference': reference,
            'checkout_url': f'https://secure.cinetpay.com/payment/{reference}',
            'metadata': {'api_key': api_key[:4] + '***', 'site_id': site_id[:4] + '***'},
        }

    def verify_webhook(self, request_body, signature, secret):
        if not secret:
            return False
        expected = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or '')

    def parse_webhook(self, payload):
        return {
            'provider_reference': payload.get('cpm_trans_id') or payload.get('transaction_id'),
            'status': 'succeeded' if str(payload.get('cpm_error_code', '')) == '00' else 'failed',
            'amount': payload.get('cpm_amount'),
            'metadata': payload,
        }


class StripeProvider(PaymentProvider):
    def create_checkout(self, payment, return_url, cancel_url):
        secret = getattr(settings, 'STRIPE_SECRET_KEY', '')
        if not secret:
            raise PaymentProviderError('Stripe non configuré')
        reference = f'pi_{secrets.token_hex(12)}'
        return {
            'provider_reference': reference,
            'checkout_url': f'https://checkout.stripe.com/c/pay/{reference}',
            'metadata': {},
        }

    def verify_webhook(self, request_body, signature, secret):
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload):
        event_type = payload.get('type', '')
        data = payload.get('data', {}).get('object', {})
        status_map = {
            'checkout.session.completed': 'succeeded',
            'payment_intent.succeeded': 'succeeded',
            'payment_intent.payment_failed': 'failed',
        }
        return {
            'provider_reference': data.get('id') or payload.get('id'),
            'status': status_map.get(event_type, 'processing'),
            'amount': data.get('amount_total') or data.get('amount'),
            'metadata': payload,
        }


class PayPalProvider(PaymentProvider):
    def create_checkout(self, payment, return_url, cancel_url):
        client_id = getattr(settings, 'PAYPAL_CLIENT_ID', '')
        if not client_id:
            raise PaymentProviderError('PayPal non configuré')
        reference = f'PAY-{uuid.uuid4().hex[:17].upper()}'
        return {
            'provider_reference': reference,
            'checkout_url': f'https://www.paypal.com/checkoutnow?token={reference}',
            'metadata': {},
        }

    def verify_webhook(self, request_body, signature, secret):
        # PayPal utilise une vérification par certificat ou ID webhook ; simplifié ici.
        return True

    def parse_webhook(self, payload):
        event_type = payload.get('event_type', '')
        resource = payload.get('resource', {})
        status = 'succeeded' if event_type.startswith('PAYMENT.CAPTURE.COMPLETED') else (
            'failed' if 'DENIED' in event_type or 'FAILED' in event_type else 'processing'
        )
        return {
            'provider_reference': resource.get('id') or payload.get('id'),
            'status': status,
            'amount': resource.get('amount', {}).get('value'),
            'metadata': payload,
        }


PROVIDERS = {
    'cinetpay': CinetPayProvider,
    'stripe': StripeProvider,
    'paypal': PayPalProvider,
}


def get_provider(provider_name):
    try:
        return PROVIDERS[provider_name]()
    except KeyError as exc:
        raise PaymentProviderError(f'Prestataire inconnu: {provider_name}') from exc
