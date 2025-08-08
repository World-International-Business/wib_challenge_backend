from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel

User = get_user_model()


class SkillLevel(models.TextChoices):
    BEGINNER = 'beginner', _('Débutant')
    INTERMEDIATE = 'intermediate', _('Intermédiaire')
    ADVANCED = 'advanced', _('Avancé')


class Course(BaseModel):
    title = models.CharField(_('Titre'), max_length=255)
    description = models.TextField(_('Description'))
    level = models.CharField(_('Niveau'), max_length=20, choices=SkillLevel.choices)
    is_free = models.BooleanField(_('Gratuit'), default=True)

    class Meta:
        verbose_name = _('Cours')
        verbose_name_plural = _('Cours')
        ordering = ['title']

    def __str__(self):
        return self.title


class Module(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name=_('Cours')
    )
    title = models.CharField(_('Titre'), max_length=255)
    description = models.TextField(_('Description'), blank=True)

    class Meta:
        verbose_name = _('Module')
        verbose_name_plural = _('Modules')
        ordering = ['course', 'title']

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class ContentType(models.TextChoices):
    VIDEO = 'video', _('Vidéo')
    PDF = 'pdf', _('Document PDF')
    TALK = 'talk', _('Conférence')
    EXTERNAL_RESOURCE = 'external', _('Ressource Externe')
    MARKDOWN = 'markdown', _('Markdown')


class Content(models.Model):
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='contents',
        verbose_name=_('Module')
    )
    title = models.CharField(_('Titre'), max_length=255)
    content_type = models.CharField(_('Content Type'), max_length=15, choices=ContentType.choices)
    resource_file = models.FileField(_('Fichier'), null=True, blank=True, upload_to='learning/contents/')
    resource_url = models.URLField(_('URL'), null=True, blank=True)
    content = models.TextField(_('Contenu'), null=True, blank=True)

    class Meta:
        verbose_name = _('Contenu')
        verbose_name_plural = _('Contenus')
        ordering = ['module', 'title']

    def clean(self):
        """Valide que les champs correspondent bien au type de contenu"""
        super().clean()
        errors = {}

        if self.content_type == ContentType.VIDEO:
            if not self.resource_file and not self.resource_url:
                msg = _('Un fichier ou une URL est requis pour le type vidéo.')
                errors['resource_file'] = msg
                errors['resource_url'] = msg
            if self.content:
                errors['content'] = _('Le champ contenu doit être vide pour le type vidéo.')

        elif self.content_type == ContentType.PDF:
            if not self.resource_file:
                errors['resource_file'] = _('Un fichier PDF est requis pour le type PDF.')
            if self.resource_url:
                errors['resource_url'] = _('Le champ URL doit être vide pour le type PDF.')
            if self.content:
                errors['content'] = _('Le champ contenu doit être vide pour le type PDF.')

        elif self.content_type == ContentType.TALK:
            if not self.resource_url:
                errors['resource_url'] = _('Une URL est requise pour le type conférence.')
            if self.resource_file:
                errors['resource_file'] = _('Le champ fichier doit être vide pour le type conférence.')
            if self.content:
                errors['content'] = _('Le champ contenu doit être vide pour le type conférence.')

        elif self.content_type == ContentType.EXTERNAL_RESOURCE:
            if not self.resource_url:
                errors['resource_url'] = _('Une URL est requise pour le type ressource externe.')
            if self.resource_file:
                errors['resource_file'] = _('Le champ fichier doit être vide pour le type ressource externe.')
            if self.content:
                errors['content'] = _('Le champ contenu doit être vide pour le type ressource externe.')

        elif self.content_type == ContentType.MARKDOWN:
            if not self.content:
                errors['content'] = _('Le contenu markdown est requis pour le type markdown.')
            if self.resource_file:
                errors['resource_file'] = _('Le champ fichier doit être vide pour le type markdown.')
            if self.resource_url:
                errors['resource_url'] = _('Le champ URL doit être vide pour le type markdown.')

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.module.title} - {self.title}"


class Quiz(models.Model):
    module = models.OneToOneField(
        Module,
        null=True,
        on_delete=models.CASCADE,
        related_name='quiz',
        verbose_name=_('Module')
    )
    title = models.CharField(_('Titre'), max_length=255)
    description = models.TextField(_('Description'), blank=True)

    class Meta:
        verbose_name = _('Quiz')
        verbose_name_plural = _('Quiz')
        ordering = ['module', 'title']

    def __str__(self):
        return f"{self.module.title} - {self.title}"


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name=_('Quiz')
    )
    title = models.CharField(_('Question'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    explanation = models.TextField(_('Explication'), blank=True)

    class Meta:
        verbose_name = _('Question de Quiz')
        verbose_name_plural = _('Questions de Quiz')
        ordering = ['quiz', 'id']

    def __str__(self):
        return self.title


class QuizChoice(models.Model):
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name=_('Question')
    )
    text = models.CharField(_('Texte'), max_length=255)
    is_correct = models.BooleanField(_('Réponse correcte'), default=False)

    class Meta:
        verbose_name = _('Choix de réponse')
        verbose_name_plural = _('Choix de réponses')
        ordering = ['question', 'id']

    def __str__(self):
        return self.text


class QuizResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Utilisateur'))
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, verbose_name=_('Quiz'))
    submitted_at = models.DateTimeField(_('Soumis le'), auto_now_add=True)
    score = models.FloatField(_('Score'), default=0)

    class Meta:
        verbose_name = _('Résultat de Quiz')
        verbose_name_plural = _('Résultats de Quiz')
        ordering = ['-submitted_at']
        unique_together = ('user', 'quiz', 'submitted_at')

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} - {self.score}"


class QuizAnswer(models.Model):
    result = models.ForeignKey(
        QuizResult,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name=_('Résultat')
    )
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        verbose_name=_('Question')
    )
    selected_choices = models.ManyToManyField(
        QuizChoice,
        verbose_name=_('Choix sélectionnés')
    )
    is_correct = models.BooleanField(_('Correct'))

    class Meta:
        verbose_name = _('Réponse de Quiz')
        verbose_name_plural = _('Réponses de Quiz')
        unique_together = ('result', 'question')


class Progress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Utilisateur'))
    content = models.ForeignKey(Content, on_delete=models.CASCADE, verbose_name=_('Contenu'))
    is_completed = models.BooleanField(_('Terminé'), default=False)
    completed_at = models.DateTimeField(_('Terminé le'), null=True, blank=True)

    class Meta:
        verbose_name = _('Progrès')
        verbose_name_plural = _('Progrès')
        unique_together = ('user', 'content')
        ordering = ['-completed_at']


class Certificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Utilisateur'))
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name=_('Cours'))
    issued_at = models.DateTimeField(_('Émis le'), auto_now_add=True)
    file = models.FileField(_('Fichier'), upload_to='certificates/')

    class Meta:
        verbose_name = _('Certificat')
        verbose_name_plural = _('Certificats')
        unique_together = ('user', 'course')
        ordering = ['-issued_at']

    def __str__(self):
        return f"Certif: {self.user.username} - {self.course.title}"
