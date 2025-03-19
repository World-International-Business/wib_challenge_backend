import os
import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class _UserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        if not extra_fields.get('first_name'):
            raise ValueError(_('The First Name field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Roles.ADMIN)

        return self.create_user(email, password, **extra_fields)


def profile_pictures_upload(instance, filename):
    if instance.pk:
        old_file = instance.__class__.objects.get(pk=instance.pk).picture
        if old_file and old_file.name:
            old_file.delete(save=False)
    return f"profiles/{uuid.uuid4()}{os.path.splitext(filename)[1]}"


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'admin', _('Administrateur')
        USER = 'dev', _('Développeur')
        ORG = 'org', _('Organisation')

    username = None
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(_('Rôle'), max_length=10, choices=Roles.choices, default=Roles.USER)
    picture = models.ImageField(_('Photo de profil'), upload_to=profile_pictures_upload, null=True, blank=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = _UserManager()

    def delete(self, **kwargs):
        self.is_active = False
        self.save()
        return self
