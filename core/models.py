from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    created_at = models.DateTimeField(_('Date de création'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Date de modification'), auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at', '-updated_at']


class Profession(BaseModel):
    title = models.CharField(_('Titre'), max_length=255, unique=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('Profession')
        verbose_name_plural = _('Professions')
        ordering = ['title']


class Technology(BaseModel):
    name = models.CharField(_('Nom'), max_length=255, unique=True)
    image = models.ImageField(_('Image'), upload_to='technologies/')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Technologie')
        verbose_name_plural = _('Technologies')
        ordering = ['name']


@receiver([post_delete, pre_save], sender=Technology)
def delete_old_image(sender, instance, **kwargs):
    if instance.pk:
        old_image = sender.objects.get(pk=instance.pk).image
        if old_image and old_image.name:
            old_image.delete(save=False)
