from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TitleSlugDescriptionModel

from apps.accounts.models import User
from apps.core.models import BaseModel, Technology


class Question(BaseModel, TitleSlugDescriptionModel):
    class Meta:
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')
        ordering = ['-created_at']

    class Difficulty(models.TextChoices):
        EASY = 'easy', _('Facile')
        MEDIUM = 'medium', _('Moyen')
        HARD = 'hard', _('Difficile')

    DIFFICULTY_WEIGHTS = {
        Difficulty.EASY: 100,
        Difficulty.MEDIUM: 300,
        Difficulty.HARD: 500,
    }

    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente de validation')
        PUBLISHED = 'published', _('Publiée')
        REJECTED = 'rejected', _('Rejetée')

    title = models.TextField(_('Titre'))
    description = models.TextField(_('Description'), blank=True, null=True)
    explanation = models.TextField(_('Explication'), help_text=_('Explication de la réponse'))
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, verbose_name=_('Difficulté'),
                                  db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name=_('Statut'),
                              db_index=True)
    publisher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions', verbose_name=_('Éditeur'))

    duration = models.IntegerField(_('Durée'), default=20, help_text=_('Durée en secondes'),
                                   validators=[MinValueValidator(20), MaxValueValidator(200)])
    technology = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name='questions',
                                   verbose_name=_('Technologie'), null=True, blank=True, db_index=True)

    weight = models.IntegerField(_('Poids'), default=100, db_index=True)

    def __str__(self):
        return self.title[:50]

    def get_weight_from_difficulty(self):
        """Calcule le poids en fonction de la difficulté"""
        return self.DIFFICULTY_WEIGHTS.get(self.difficulty, 0)


@receiver(pre_save, sender=Question)
def set_question_weight(sender, instance, **kwargs):
    """Met à jour automatiquement le poids en fonction de la difficulté"""
    instance.weight = instance.get_weight_from_difficulty()


class Choice(BaseModel):
    class Meta:
        verbose_name = _('Choix')
        verbose_name_plural = _('Choix')
        indexes = [
            models.Index(fields=['question', 'is_correct']),
        ]

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices', verbose_name=_('Question'))
    text = models.TextField(_('Texte'))
    is_correct = models.BooleanField(_('Est correct'), default=False)

    def __str__(self):
        return f"{self.text[:30]}... - {'Correct' if self.is_correct else 'Incorrect'}"
