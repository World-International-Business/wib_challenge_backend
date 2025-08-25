from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Organization(models.Model):
    class Meta:
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')

    name = models.CharField(_('Nom'), max_length=255)
    description = models.TextField(_('Description'), blank=True, null=True)
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organization',
                                   verbose_name=_('Compte'))
    logo = models.ImageField(_('Logo'), upload_to='companies/logos/', blank=True, null=True)
    website = models.URLField(_('Site web'), blank=True)
    address = models.CharField(_('Adresse'), max_length=255, blank=True)
    city = models.CharField(_('Ville'), max_length=100, blank=True)
    country = models.CharField(_('Pays'), max_length=100, blank=True)
    created_at = models.DateTimeField(_('Date de création'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Date de mise à jour'), auto_now=True)

    def __str__(self):
        return self.name
