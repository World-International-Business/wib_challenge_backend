from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, Profession, Language, delete_old_image


def validate_language(value):
    if any(part.strip() not in Language.values for part in value.strip().split(',') if part):
        raise ValidationError(_('Invalid language code. Supported codes are: fr, en, es.'))


def _upload_to(instance, filename):
    return f'evaluations/{slugify(instance.title)}/{filename}'


class Evaluation(BaseModel):
    class QuestionOrder(models.TextChoices):
        RANDOM = 'random', _('Aléatoire')
        TECHNO = 'techno', _('Par technologie')
        ADDED = 'added', _('Par date d\'ajout')

    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', _('Débutant 0- 2 ans d\'expérience')
        INTERMEDIATE = 'intermediate', _('Intermédiaire 3-5 ans d\'expérience')
        EXPERT = 'expert', _('Expert 5+ ans d\'expérience')

    title = models.CharField(_('Title'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    slug = models.SlugField(_('Slug'), max_length=255, unique=True)
    image = models.ImageField(_('Image'), upload_to=_upload_to, blank=True, null=True)
    technologies = models.ManyToManyField('core.Technology', related_name='evaluations', verbose_name=_('Technologies'))
    questions_order = models.CharField(_('Ordre des questions'), choices=QuestionOrder.choices,
                                       default=QuestionOrder.RANDOM, max_length=20)
    languages = models.CharField(_('Language'), max_length=10, default=Language.FRENCH.value,
                                 validators=[validate_language])
    profession = models.ForeignKey(Profession, on_delete=models.CASCADE, related_name='evaluations',
                                   verbose_name=_('Profession'))
    difficulty = models.CharField(_('Difficulty'), choices=Difficulty.choices,
                                  default=Difficulty.BEGINNER, max_length=20)

    class Meta:
        verbose_name = _('Evaluation')
        verbose_name_plural = _('Evaluations')
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


receiver([pre_save, pre_delete], sender=Evaluation)(delete_old_image)
