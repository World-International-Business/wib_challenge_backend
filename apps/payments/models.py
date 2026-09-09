import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    class Purpose(models.TextChoices):
        COURSE_ENROLLMENT = 'course_enrollment', _('Inscription à une formation')
        CERTIFICATE = 'certificate', _('Attestation/certificat')

    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente')
        PROCESSING = 'processing', _('En cours')
        SUCCEEDED = 'succeeded', _('Réussi')
        FAILED = 'failed', _('Échoué')
        CANCELLED = 'cancelled', _('Annulé')
        REFUNDED = 'refunded', _('Remboursé')

    class Provider(models.TextChoices):
        CINETPAY = 'cinetpay', 'CinetPay'
        STRIPE = 'stripe', 'Stripe'
        PAYPAL = 'paypal', 'PayPal'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    purpose = models.CharField(_('Objet'), max_length=30, choices=Purpose.choices)
    course = models.ForeignKey('learning.Course', on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    certificate = models.ForeignKey('learning.Certificate', on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(_('Montant'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('Devise'), max_length=3, default='XOF')
    provider = models.CharField(_('Prestataire'), max_length=20, choices=Provider.choices)
    provider_reference = models.CharField(_('Référence prestataire'), max_length=255, blank=True, db_index=True)
    status = models.CharField(_('Statut'), max_length=20, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.CharField(_('Raison d\'échec'), max_length=255, blank=True)
    metadata = models.JSONField(_('Métadonnées'), default=dict, blank=True)
    paid_at = models.DateTimeField(_('Payé le'), null=True, blank=True)
    checkout_url = models.URLField(_('URL de paiement'), blank=True)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)
    webhook_payload = models.JSONField(_('Payload webhook'), default=dict, blank=True)
    webhook_signature = models.CharField(_('Signature webhook'), max_length=500, blank=True)

    class Meta:
        verbose_name = _('Paiement')
        verbose_name_plural = _('Paiements')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['provider', 'provider_reference']),
            models.Index(fields=['course', 'purpose']),
        ]

    def __str__(self):
        return f"{self.provider} {self.amount} {self.currency} ({self.status})"
