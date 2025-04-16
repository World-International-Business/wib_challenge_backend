from django.db import models
from django.utils.translation import gettext_lazy as _


class ExperienceLevel(models.IntegerChoices):
    BEGINNER = 1, _('Débutant')
    INTERMEDIATE = 2, _('Intermédiaire')
    EXPERT = 3, _('Expert')
