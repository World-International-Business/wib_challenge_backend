from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, Profession, delete_old_image
from questions.models import Question, Choice


def _upload_to(instance, filename):
    """Détermine le chemin de stockage des images d'évaluations"""
    return f'evaluations/{slugify(instance.title)}/{filename}'


class EvaluationType(models.TextChoices):
    NORMAL = 'normal', _('Normal')
    COMPETITION = 'competition', _('Competition')


class Evaluation(BaseModel):
    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', _('Débutant 0- 2 ans d\'expérience')
        INTERMEDIATE = 'intermediate', _('Intermédiaire 3-5 ans d\'expérience')
        EXPERT = 'expert', _('Expert 5+ ans d\'expérience')

    title = models.CharField(_('Title'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    slug = models.SlugField(_('Slug'), max_length=255,
                            unique=True, db_index=True)
    image = models.ImageField(
        _('Image'), upload_to=_upload_to, blank=True, null=True)
    technology = models.ForeignKey('core.Technology', related_name='evaluations', verbose_name=_('Technologie'),
                                   on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    profession = models.ForeignKey(Profession, on_delete=models.CASCADE, related_name='evaluations',
                                   verbose_name=_('Profession'), null=True, blank=True, db_index=True)
    difficulty = models.CharField(_('Difficulty'), choices=Difficulty.choices, default=Difficulty.BEGINNER,
                                  max_length=20, db_index=True)
    publisher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('Créateur'),
                                  related_name='evaluations', db_index=True)

    evaluation_type = models.CharField(_('Type'), choices=EvaluationType.choices, default=EvaluationType.NORMAL,
                                       max_length=20, db_index=True)

    class Meta:
        verbose_name = _('Evaluation')
        verbose_name_plural = _('Evaluations')
        ordering = ['-created_at']
        indexes = [models.Index(fields=['slug']),
                   models.Index(fields=['difficulty']), ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def is_constructed(self):
        """Détermine si l'évaluation a assez de questions publiées"""
        return self.questions.filter(status=Question.Status.PUBLISHED).count() >= 20


class SubmissionAttempt(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                   related_name='attempts', db_index=True)
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('Utilisateur'),
                                  related_name='attempts', db_index=True)
    submission = models.OneToOneField('Submission', on_delete=models.CASCADE, verbose_name=_('Soumission'),
                                      related_name='attempt', blank=True, null=True)
    started_at = models.DateTimeField(
        _('Commencé le'), auto_now_add=True, db_index=True)
    ended_at = models.DateTimeField(_('Terminé le'), blank=True, null=True)
    questions = models.ManyToManyField(Question, verbose_name=_(
        'Questions'), blank=True, related_name='attempts')

    class Meta:
        verbose_name = _('Tentative de soumission')
        verbose_name_plural = _('Tentatives de soumission')
        indexes = [models.Index(fields=['started_at']), ]

    def __str__(self):
        return f'{self.candidate} - {self.evaluation} - {self.started_at}'

    @property
    def is_finished(self):
        return self.ended_at is not None and self.submission is not None


class Submission(models.Model):
    # Retrait de max_length inutile pour FloatField
    score = models.FloatField(_('Résultat'), blank=True, null=True)
    submitted_at = models.DateTimeField(
        _('Soumis le'), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('Soumission')
        verbose_name_plural = _('Soumissions')
        ordering = ['-submitted_at']
        indexes = [models.Index(fields=['score']), ]

    def __str__(self):
        return f'{self.score} - {self.submitted_at}'


class Answer(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente de correction')
        DISCARDED = 'discarded', _('Abandonnée')
        TIMEOUT = 'timeout', _('Timeout')
        PARTIAL = 'partial', _('Correct partiellement')
        CORRECT = 'correct', _('Correcte')
        INCORRECT = 'incorrect', _('Incorrecte')

    attempt = models.ForeignKey(SubmissionAttempt, on_delete=models.CASCADE, verbose_name=_('Tentative de soumission'),
                                related_name='answers', db_index=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name=_('Question'), related_name='answers',
                                 db_index=True)
    selected_choices = models.ManyToManyField(Choice, verbose_name=_('Choix sélectionnés'), blank=True,
                                              related_name='answers')
    is_correct = models.BooleanField(
        _('Correcte'), blank=True, null=True, db_index=True)
    answered_at = models.DateTimeField(
        _('Répondu le'), auto_now_add=True, db_index=True)
    delta_time = models.PositiveSmallIntegerField(
        _('Durée'), validators=[MaxValueValidator(200)])
    status = models.CharField(_('Statut'), choices=Status.choices,
                              default=Status.PENDING, max_length=20, db_index=True)
    score = models.IntegerField(_('Résultat'), default=0)

    class Meta:
        verbose_name = _('Réponse')
        verbose_name_plural = _('Réponses')
        unique_together = ('attempt', 'question')
        indexes = [models.Index(fields=['status']),
                   models.Index(fields=['is_correct'])]

    @property
    def corrected(self):
        return self.is_correct is not None

    def __str__(self):
        return f'{self.question}'


class Competition(models.Model):
    evaluation = models.OneToOneField(Evaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                      limit_choices_to={'evaluation_type': EvaluationType.COMPETITION},
                                      related_name='competition')

    started_at = models.DateTimeField(_('Commencé le'), blank=True, null=True)
    ended_at = models.DateTimeField(_('Terminé le'), blank=True, null=True)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        verbose_name = _('Competition')
        verbose_name_plural = _('Competitions')
        ordering = ['-created_at']


receiver([pre_save, pre_delete], sender=Evaluation)(delete_old_image)
