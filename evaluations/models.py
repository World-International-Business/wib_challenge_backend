from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, Profession, Language, delete_old_image
from questions.models import Question, Choice


def validate_language(value):
    if any(part.strip() not in Language.values for part in value.strip().split(',') if part):
        raise ValidationError(_('Invalid language code. Supported codes are: fr, en, es.'))


def _upload_to(instance, filename):
    return f'evaluations/{slugify(instance.title)}/{filename}'


class Evaluation(BaseModel):
    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', _('Débutant 0- 2 ans d\'expérience')
        INTERMEDIATE = 'intermediate', _('Intermédiaire 3-5 ans d\'expérience')
        EXPERT = 'expert', _('Expert 5+ ans d\'expérience')

    title = models.CharField(_('Title'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    slug = models.SlugField(_('Slug'), max_length=255, unique=True)
    image = models.ImageField(_('Image'), upload_to=_upload_to, blank=True, null=True)
    technology = models.ForeignKey('core.Technology', related_name='evaluations', verbose_name=_('Technologie'),
                                   on_delete=models.CASCADE, null=True, blank=True)

    profession = models.ForeignKey(Profession, on_delete=models.CASCADE, related_name='evaluations',
                                   verbose_name=_('Profession'), null=True, blank=True)
    difficulty = models.CharField(_('Difficulty'), choices=Difficulty.choices,
                                  default=Difficulty.BEGINNER, max_length=20)

    class Meta:
        verbose_name = _('Evaluation')
        verbose_name_plural = _('Evaluations')
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class SubmissionAttempt(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                   related_name='attempts')
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('Utilisateur'),
                                  related_name='attempts')
    submission = models.OneToOneField('Submission', on_delete=models.CASCADE, verbose_name=_('Soumission'),
                                      related_name='attempt', blank=True, null=True)
    started_at = models.DateTimeField(_('Commencé le'), auto_now_add=True)
    ended_at = models.DateTimeField(_('Terminé le'), blank=True, null=True)
    questions = models.ManyToManyField(Question, verbose_name=_('Questions'), blank=True, related_name='attempts')

    class Meta:
        verbose_name = _('Tentative de soumission')
        verbose_name_plural = _('Tentatives de soumission')

    def __str__(self):
        return f'{self.candidate} - {self.evaluation} - {self.started_at}'

    @property
    def is_finished(self):
        return self.ended_at is not None


class Submission(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                   related_name='submissions')
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('Utilisateur'),
                                  related_name='submissions')
    score = models.FloatField(_('Résultat'), blank=True, null=True, max_length=20)
    submitted_at = models.DateTimeField(_('Soumis le'), auto_now_add=True)

    class Meta:
        verbose_name = _('Soumission')
        verbose_name_plural = _('Soumissions')
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.candidate} - {self.evaluation} - {self.submitted_at}'


class Answer(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente de correction')
        DISCARDED = 'discarded', _('Abandonnée')
        TIMEOUT = 'timeout', _('Timeout')
        PARTIAL = 'partial', _('Correct partiellement')
        CORRECT = 'correct', _('Correcte')
        INCORRECT = 'incorrect', _('Incorrecte')

    attempt = models.ForeignKey(SubmissionAttempt, on_delete=models.CASCADE, verbose_name=_('Tentative de soumission'),
                                related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name=_('Question'), related_name='answers')
    selected_choices = models.ManyToManyField(Choice, verbose_name=_('Choix sélectionnés'), blank=True,
                                              related_name='submissions')
    is_correct = models.BooleanField(_('Correcte'), blank=True, null=True)
    answered_at = models.DateTimeField(_('Répondu le'), auto_now_add=True)
    delta_time = models.PositiveSmallIntegerField(_('Durée'), validators=[MaxValueValidator(200)])
    status = models.CharField(_('Statut'), choices=Status.choices, default=Status.PENDING, max_length=20)
    score = models.IntegerField(_('Résultat'), default=0)

    class Meta:
        verbose_name = _('Réponse')
        verbose_name_plural = _('Réponses')

    @property
    def corrected(self):
        return self.is_correct is not None

    # @property
    # def average_score(self) -> float:
    #     if not self.corrected:
    #         return 0.0
    #     if self.question.is_open_answer:
    #         return 1 if bool(self.is_correct) else 0
    #     correct_choices = self.question.choices.filter(is_correct=True)
    #     selected_ids = [choice.id for choice in self.selected_choices.all()]
    #     correct_count = correct_choices.filter(id__in=selected_ids).count()
    #     return correct_count / correct_choices.count()

    def __str__(self):
        return f'{self.question}'


receiver([pre_save, pre_delete], sender=Evaluation)(delete_old_image)
