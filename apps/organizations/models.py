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


class Notification(models.Model):
    class Types(models.TextChoices):
        INTERVIEW_REMINDER = 'interview_reminder', _("Rappel d'entretien")
        TEST_COMPLETED = 'test_completed', _("Test terminé")
        NEW_APPLICATION = 'new_application', _("Nouvelle candidature")

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='notifications', verbose_name=_('Organisation')
    )
    type = models.CharField(_('Type de notification'), max_length=50, choices=Types.choices)
    title = models.CharField(_('Titre'), max_length=255)
    message = models.TextField(_('Message'))
    is_read = models.BooleanField(_('Lu'), default=False)
    created_at = models.DateTimeField(_('Date de création'), auto_now_add=True)

    related_application = models.ForeignKey(
        'jobs.JobApplication', on_delete=models.CASCADE, related_name='notifications', verbose_name=_('Candidature associée'),
        null=True, blank=True
    )
    related_evaluation = models.ForeignKey(
        'evaluations.Evaluation', on_delete=models.CASCADE, related_name='notifications', verbose_name=_('Évaluation associée'),
        null=True, blank=True
    )

    class Meta:
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_type_display()}] {self.title}"
