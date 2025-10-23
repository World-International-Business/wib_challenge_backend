from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Organization(models.Model):
    class Meta:
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')

    COMPANY_SIZE_CHOICES = [
        ('micro', _('Micro-entreprise (1 à 9 employés)')),
        ('small', _('Petite entreprise (10 à 49 employés)')),
        ('medium', _('Entreprise moyenne (50 à 249 employés)')),
        ('large', _('Grande entreprise (250 à 999 employés)')),
        ('enterprise', _('Très grande entreprise (1000+ employés)')),
    ]

    name = models.CharField(_('Nom'), max_length=255)
    sector = models.CharField(_("Secteur d'activité"), max_length=255, blank=True)
    company_size = models.CharField(_("Taille de l'entreprise"), max_length=20, choices=COMPANY_SIZE_CHOICES, blank=True, null=True)
    email = models.EmailField(_("Email de l'entreprise"), blank=True)
    phone = models.CharField(_("Téléphone de l'entreprise"), max_length=20, blank=True)
    website = models.URLField(_('Site web'), blank=True)
    country = models.CharField(_('Pays'), max_length=100, blank=True)
    city = models.CharField(_('Ville'), max_length=100, blank=True)
    neighborhood = models.CharField(_('Quartier'), max_length=255, blank=True)
    description = models.TextField(_('Description'), blank=True, null=True)
    logo = models.ImageField(_('Logo'), upload_to='companies/logos/', blank=True, null=True)
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organization',
                                   verbose_name=_('Compte'))
    created_at = models.DateTimeField(_('Date de création'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Date de mise à jour'), auto_now=True)

    def __str__(self):
        return self.name
