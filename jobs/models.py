from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from organizations.models import Organization, ExperienceLevel


class JobCategory(models.Model):
    """
    Modèle représentant les catégories de postes (ex: Développement, Marketing, Finance).
    Permet de classer les offres d'emploi par domaine d'expertise.
    """
    name = models.CharField(_("Nom de la catégorie"), max_length=100)
    slug = models.SlugField(_("Slug URL"), max_length=120, unique=True)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("Catégorie d'emploi")
        verbose_name_plural = _("Catégories d'emploi")
        ordering = ['name']

    def __str__(self):
        return self.name


class JobOffer(models.Model):
    """
    Modèle principal pour les offres d'emploi.
    Contient toutes les informations relatives à un poste proposé par une entreprise.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Brouillon')
        PUBLISHED = 'published', _('Publié')
        EXPIRED = 'expired', _('Expiré')
        FILLED = 'filled', _('Fermé')

    class JobType(models.TextChoices):
        FULL_TIME = 'full_time', _('Temps plein')
        PART_TIME = 'part_time', _('Temps partiel')
        CDI = 'cdi', _('CDI')
        CDD = 'cdd', _('CDD')
        INTERNSHIP = 'internship', _('Stage')
        REMOTE = 'remote', _('Télétravail')
        FREELANCE = 'freelance', _('Freelance')

    title = models.CharField(_("Titre du poste"), max_length=255)
    slug = models.SlugField(_("Slug URL"), max_length=255, unique=True)
    company = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='job_offers',
                                verbose_name=_("Entreprise"))
    category = models.ForeignKey(JobCategory, on_delete=models.PROTECT, related_name='job_offers',
                                 verbose_name=_("Catégorie"))
    description = models.TextField(_("Description du poste"))
    responsibilities = models.TextField(_("Responsabilités"), blank=True)
    requirements = models.TextField(_("Prérequis"))
    benefits = models.TextField(_("Avantages"), blank=True)
    salary_min = models.DecimalField(_("Salaire minimum"), max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(_("Salaire maximum"), max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(_("Devise"), max_length=3, default='EUR')
    job_type = models.CharField(_("Type de contrat"), max_length=20, choices=JobType.choices)
    experience_level = models.CharField(_("Niveau d'expérience"), max_length=20, choices=ExperienceLevel.choices)
    location = models.CharField(_("Localisation"), max_length=255)
    remote_allowed = models.BooleanField(_("Télétravail autorisé"), default=False)
    application_url = models.URLField(_("URL de candidature"), blank=True)
    application_email = models.EmailField(_("Email pour candidature"), blank=True)
    status = models.CharField(_("Statut"), max_length=20, choices=Status.choices, default=Status.DRAFT)
    featured = models.BooleanField(_("Mise en avant"), default=False)
    created_at = models.DateTimeField(_("Date de création"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Date de mise à jour"), auto_now=True)
    published_at = models.DateTimeField(_("Date de publication"), null=True, blank=True)
    expires_at = models.DateTimeField(_("Date d'expiration"), null=True, blank=True)

    class Meta:
        verbose_name = _("Offre d'emploi")
        verbose_name_plural = _("Offres d'emploi")
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug or not self.pk:
            super().save(*args, **kwargs)
            self.slug = f"{self.id}-{slugify(self.title)}"
            self.save(update_fields=['slug'])
        else:
            super().save(*args, **kwargs)


class JobApplication(BaseModel):
    """
    Modèle pour les applications d'emploi.
   """
    job_offer = models.ForeignKey(JobOffer, on_delete=models.CASCADE, related_name='applications',
                                  verbose_name=_("Offre d'emploi"))

    applicant_name = models.CharField(_("Nom du candidat"), max_length=255)
    applicant_email = models.EmailField(_("Email du candidat"))
    resume = models.FileField(_("CV"), upload_to='resumes/', blank=True, null=True)
    cover_letter = models.TextField(_("Lettre de motivation"), blank=True)
    ai_analysis = models.TextField(_("Analyse IA du CV"), blank=True)
    ai_decision = models.BooleanField(_("Décision IA"), null=True, blank=True)
    submitted_at = models.DateTimeField(_("Date de soumission"), auto_now_add=True)

    class Meta:
        verbose_name = _("Candidature")
        verbose_name_plural = _("Candidatures")
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.applicant_name} - {self.job_offer.title}"
