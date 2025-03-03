from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class _UserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        if not extra_fields.get('first_name'):
            raise ValueError(_('The First Name field must be set'))
        if not extra_fields.get('last_name'):
            raise ValueError(_('The Last Name field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class ExperienceLevel(models.IntegerChoices):
        BEGINNER = 1, _('Débutant')
        INTERMEDIATE = 2, _('Intermédiaire')
        ADVANCED = 3, _('Avancé')
        EXPERT = 4, _('Expert')

    username = None
    email = models.EmailField(_("email address"), unique=True)
    domain = models.ForeignKey('challenges.Domain', on_delete=models.SET_NULL, null=True, blank=True)
    challenges = models.ManyToManyField('challenges.Challenge', related_name='users', blank=True)
    experience_level = models.IntegerField('Expérience', choices=ExperienceLevel.choices,
                                           default=ExperienceLevel.BEGINNER)
    experience = models.IntegerField('Années d\'expérience', default=0)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = _UserManager()

    def delete(self, **kwargs):
        self.is_active = False
        self.save()
        return self
