import os
import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class _UserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
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
    # Évite une requête DB inutile si c'est un nouvel utilisateur
    if not (not instance.pk or not hasattr(instance, '_original_picture_path') or not instance._original_picture_path):
        if os.path.exists(instance._original_picture_path):
            try:
                os.remove(instance._original_picture_path)
            except (FileNotFoundError, PermissionError):
                pass
    return f"profiles/{uuid.uuid4()}{os.path.splitext(filename)[1]}"


class User(AbstractUser):
    class Meta(AbstractUser.Meta):
        ordering = ['first_name', 'last_name', 'email']

    class Roles(models.TextChoices):
        ADMIN = 'admin', _('Administrateur')
        USER = 'dev', _('Développeur')
        ORG = 'org', _('Organisation')

    username = models.UUIDField(_('username'), unique=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(_('Rôle'), max_length=10, choices=Roles.choices, default=Roles.USER)
    picture = models.ImageField(_('Photo de profil'), upload_to=profile_pictures_upload, null=True, blank=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name']

    objects = _UserManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_picture_path = self.picture.path if self.pk and self.picture else None

    def delete(self, **kwargs):
        self.is_active = False
        self.save(update_fields=['is_active'])
        return self

    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN

    @property
    def is_org(self):
        return self.role == self.Roles.ORG

    @property
    def is_dev(self):
        return self.role == self.Roles.USER
