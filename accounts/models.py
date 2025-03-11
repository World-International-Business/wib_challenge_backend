from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from questions.models import Tag
from wib_challenge.enums import ExperienceLevel


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
    username = None
    email = models.EmailField(_("email address"), unique=True)
    domain = models.ForeignKey('questions.Domain', on_delete=models.SET_NULL, null=True, blank=True)
    challenges = models.ManyToManyField('challenges.Challenge', related_name='users', blank=True)
    experience_level = models.IntegerField('Expérience', choices=ExperienceLevel.choices,
                                           default=ExperienceLevel.BEGINNER)
    experience = models.IntegerField('Années d\'expérience', default=0)
    skills = models.ManyToManyField('questions.Tag', related_name='users', blank=True, verbose_name="Compétences",
                                    through='UserSkill')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = _UserManager()

    def delete(self, **kwargs):
        self.is_active = False
        self.save()
        return self

    @property
    def has_skill_infos(self):
        return self.skills.exists()


class UserSkill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.ForeignKey(Tag, on_delete=models.CASCADE)
    experience_level = models.IntegerField(choices=ExperienceLevel.choices, default=ExperienceLevel.BEGINNER)

    class Meta:
        unique_together = ('user', 'skill')

    def __str__(self):
        return f"{self.user.email} - {self.skill.name} ({self.get_experience_level_display()})"
