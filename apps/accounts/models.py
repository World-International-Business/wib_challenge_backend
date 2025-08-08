import os
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import validate_email
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class _UserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Roles.ADMIN)

        if not extra_fields.get('is_staff'):
            raise ValueError(_('Superuser must have is_staff=True.'))
        if not extra_fields.get('is_superuser'):
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

    def active_users(self):
        return self.filter(is_active=True)

    def by_role(self, role):
        return self.filter(role=role)

    def recent_users(self, days=30):
        return self.filter(date_joined__gte=timezone.now() - timedelta(days=days))


def profile_pictures_upload(instance, filename):
    if instance.pk and hasattr(instance, '_original_picture_path') and instance._original_picture_path:
        try:
            if os.path.exists(instance._original_picture_path):
                os.remove(instance._original_picture_path)
        except (FileNotFoundError, PermissionError, OSError):
            pass

    ext = os.path.splitext(filename)[1].lower()
    return f"profiles/{instance.role}/{uuid.uuid4()}{ext}"


class User(BaseModel, AbstractUser):
    class Meta(AbstractUser.Meta):
        ordering = ['first_name', 'last_name', 'email']
        verbose_name = _('Utilisateur')
        verbose_name_plural = _('Utilisateurs')

    class Roles(models.TextChoices):
        ADMIN = 'admin', _('Administrateur')
        USER = 'developer', _('Développeur')
        ORGANIZATION = 'organization', _('Organisation')
        EVALUATOR = 'evaluator', _('Évaluateur')

    username = models.UUIDField(_('username'), unique=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("Adresse email"), unique=True, validators=[validate_email])
    role = models.CharField(_('Rôle'), max_length=20, choices=Roles.choices, default=Roles.USER)
    picture = models.ImageField(
        _('Photo de profil'),
        upload_to=profile_pictures_upload,
        null=True,
        blank=True,
        help_text=_('Image recommandée : 300x300px, formats acceptés: JPG, PNG')
    )
    phone = models.CharField(_('Téléphone'), max_length=20, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name']

    objects = _UserManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_picture_path = self.picture.path if self.pk and self.picture else None

    def save(self, *args, **kwargs):
        if not self.first_name.strip():
            raise ValueError(_('Le prénom est obligatoire'))

        if self.email:
            self.email = self.email.lower().strip()

        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Soft delete — désactive l'utilisateur au lieu de le supprimer"""
        self.is_active = False
        self.save(update_fields=['is_active'])
        return self

    def hard_delete(self, using=None, keep_parents=False):
        """Suppression définitive de l'utilisateur"""
        if self.picture:
            try:
                if os.path.exists(self.picture.path):
                    os.remove(self.picture.path)
            except (FileNotFoundError, OSError):
                pass
        return super().delete(using=using, keep_parents=keep_parents)

    @property
    def full_name(self):
        return self.get_full_name()

    @property
    def initials(self):
        """Retourne les initiales de l'utilisateur"""
        return f"{self.first_name[0] if self.first_name else ''}{self.last_name[0] if self.last_name else ''}".upper()

    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN

    @property
    def is_org(self):
        return self.role == self.Roles.ORGANIZATION

    @property
    def is_dev(self):
        return self.role == self.Roles.USER

    @property
    def is_evaluator(self):
        return self.role == self.Roles.EVALUATOR

    def is_recently_joined(self, days=7):
        """Vérifie si l'utilisateur s'est inscrit récemment"""
        return self.date_joined >= timezone.now() - timedelta(days=days)

    def __str__(self):
        return f"{self.full_name} ({self.email})"
