from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from core.models import BaseModel, Technology, Language


# TODO add  votes and comments and comments likes and test foreign key
class Question(BaseModel):
    class Meta:
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')
        ordering = ['-created_at']

    class Difficulty(models.TextChoices):
        EASY = 'easy', _('Facile')
        MEDIUM = 'medium', _('Moyen')
        HARD = 'hard', _('Difficile')
        EXPERT = 'expert', _('Expert')

    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente de validation')
        PUBLISHED = 'published', _('Publiée')
        REJECTED = 'rejected', _('Rejetée')

    text = models.TextField(_('Titre'))
    explanation = models.TextField(_('Explication'), help_text=_('Explication de la réponse'))
    language = models.CharField(max_length=10, choices=Language.choices, verbose_name=_('Langue'))
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, verbose_name=_('Difficulté'))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name=_('Statut'))
    publisher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions', verbose_name=_('Éditeur'))
    evaluation = models.ForeignKey('evaluations.Evaluation', on_delete=models.CASCADE, related_name='questions',
                                   verbose_name=_('Évaluation'))  # TODO add evaluation to serializer
    translated = models.OneToOneField('self', on_delete=models.CASCADE, related_name='original', null=True,
                                      verbose_name=_('Question en anglais'))
    duration = models.IntegerField(_('Durée'), default=20, help_text=_('Durée en secondes'),
                                   validators=[MinValueValidator(20), MaxValueValidator(200)])
    technology = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name='questions',
                                   verbose_name=_('Technologie'))

    def __str__(self):
        return self.text


class Choice(BaseModel):
    class Meta:
        verbose_name = _('Choix')
        verbose_name_plural = _('Choix')

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices', verbose_name=_('Question'))
    text = models.TextField(_('Texte'))
    is_correct = models.BooleanField(_('Est correct'), default=False)

    def __str__(self):
        return self.text + '-' + _('Correct') if self.is_correct else _('Incorrect')
