import os
import uuid

from django.conf import settings
from django.core import validators
from django.db import models
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from core.models import Profession, BaseModel, Technology, delete_old_image

min_max_validator = [
    validators.MaxValueValidator(100),
    validators.MinValueValidator(0)
]


class CandidateProfile(BaseModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile',
                                verbose_name=_('Utilisateur'), unique=True)

    profession = models.ForeignKey(Profession, on_delete=models.PROTECT, verbose_name=_('Profession'))
    location = models.CharField(_('Localisation'), max_length=255, blank=True)
    short_bio = models.TextField(_('Courte biographie'), max_length=255, blank=True)
    biography = models.TextField(_('Biographie'), blank=True)
    disability = models.BooleanField(_('Handicap'), default=False)

    years_experience = models.PositiveSmallIntegerField(_('Expérience professionnelle'), null=True)
    other_years_experience = models.PositiveSmallIntegerField(_('Autre expérience'), null=True)

    highest_degree = models.PositiveSmallIntegerField(_('Diplôme le plus élevé'), null=True, help_text=_('Bac + X'))

    technologies = models.ManyToManyField(Technology, related_name='profiles', verbose_name=_('Technologies'),
                                          through='ProfileTechnology')

    interested_by = models.CharField(_('Intéressé par'), max_length=512, blank=True)

    # TODO add links to profile ( name, url)

    def __str__(self):
        return self.user.get_full_name()

    class Meta:
        verbose_name = _('Profil')
        verbose_name_plural = _('Profils')
        ordering = ('user__first_name', '-created_at', 'profession__title')


class Experience(BaseModel):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='experiences',
                                verbose_name=_('Profil'))
    title = models.CharField(_('Titre'), max_length=255)
    company = models.CharField(_('Entreprise'), max_length=255)
    location = models.CharField(_('Localisation'), max_length=255)
    start_date = models.DateField(_('Date de début'))
    end_date = models.DateField(_('Date de fin'), null=True, blank=True)
    description = models.TextField(_('Description'))
    still_working = models.BooleanField(_('Toujours en poste'), default=False)

    def __str__(self):
        return f"{self.title} - {self.company}"

    class Meta:
        verbose_name = _('Expérience professionnelle')
        verbose_name_plural = _('Expériences professionnelles')
        ordering = ('-start_date', '-end_date', 'title', 'company')


class Education(BaseModel):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='educations',
                                verbose_name=_('Profil'))
    name = models.CharField(_('Nom'), max_length=255)
    year_of_graduation = models.PositiveSmallIntegerField(_('Année de diplomation'))
    speciality = models.CharField(_('Spécialité'), max_length=255, null=True, blank=True)
    diploma = models.CharField(_('Diplôme'), max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Formation')
        verbose_name_plural = _('Formations')
        ordering = ('-year_of_graduation', 'name')


class Language(BaseModel):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='languages',
                                verbose_name=_('Profile'))
    name = models.CharField(_('Nom'), max_length=255, unique=True)
    level = models.PositiveSmallIntegerField(_('Niveau'), default=0, validators=min_max_validator)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Langue')
        verbose_name_plural = _('Langues')
        ordering = ('name', 'level')


class Project(BaseModel):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='projects',
                                verbose_name=_('Projet'))
    name = models.CharField(_('Nom'), max_length=255)
    description = models.TextField(_('Description'))
    start_date = models.DateField(_('Date de début'))
    link = models.URLField(_('Lien'), null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Projet')
        verbose_name_plural = _('Projets')


def upload_image_to(instance, filename):
    if instance.pk:
        old_file = instance.__class__.objects.get(pk=instance.pk).image
        if old_file and old_file.name:
            old_file.delete(save=False)
    return f"projects/{instance.project.pk}/{uuid.uuid4()}{os.path.splitext(filename)[1]}"


class ProjectImage(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images', verbose_name=_('Projet'))
    image = models.ImageField(_('Image'), upload_to=upload_image_to)

    class Meta:
        verbose_name = _('Image de projet')
        verbose_name_plural = _('Images de projet')


class ProfileTechnology(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='profile_technologies',
                                verbose_name=_('Profil'))
    technology = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name='profile_technologies',
                                   verbose_name=_('Technologie'))

    level = models.PositiveSmallIntegerField(_('Niveau'), default=0, validators=min_max_validator)

    class Meta:
        verbose_name = _('Technologie de profil')
        verbose_name_plural = _('Technologies de profil')
        unique_together = ('profile', 'technology')
        ordering = ('id',)


receiver([pre_delete, pre_save], sender=ProjectImage)(delete_old_image)
