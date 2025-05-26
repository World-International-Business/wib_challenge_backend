from xml import dom
from django.db import models
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    created_at = models.DateTimeField(_('Date de création'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Date de modification'), auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at', '-updated_at']


class Domain(BaseModel):
    name = models.CharField(_('Nom'), max_length=255, unique=True)
    description = models.TextField(_('Description'), blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Domaine')
        verbose_name_plural = _('Domaines')
        ordering = ['name']


class Technology(BaseModel):
    name = models.CharField(_('Nom'), max_length=255, unique=True)
    image = models.ImageField(_('Image'), upload_to='technologies/')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Technologie')
        verbose_name_plural = _('Technologies')
        ordering = ['name']


class Profession(BaseModel):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='professions', verbose_name=_('Domaine'))
    title = models.CharField(_('Titre'), max_length=255, unique=True)
    technologies = models.ManyToManyField(Technology, verbose_name=_('Technologies'), related_name='professions')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('Profession')
        verbose_name_plural = _('Professions')
        ordering = ['title']


@receiver([pre_delete, pre_save], sender=Technology)
def delete_old_image(sender, instance, **kwargs):
    if instance.pk:
        old_image = sender.objects.get(pk=instance.pk).image
        if old_image and old_image.name:
            old_image.delete(save=False)
