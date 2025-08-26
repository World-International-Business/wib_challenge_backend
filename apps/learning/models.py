from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TitleSlugDescriptionModel

from apps.core.models import BaseModel, Technology

User = get_user_model()


class SkillLevel(models.TextChoices):
    BEGINNER = 'beginner', _('Débutant')
    INTERMEDIATE = 'intermediate', _('Intermédiaire')
    ADVANCED = 'advanced', _('Avancé')


class LearningModel(BaseModel, TitleSlugDescriptionModel):
    class Meta:
        abstract = True


class Course(LearningModel):
    title = models.CharField(_('Titre'), max_length=255)
    description = models.TextField(_('Description'))
    level = models.CharField(_('Niveau'), max_length=20, choices=SkillLevel.choices)
    is_free = models.BooleanField(_('Gratuit'), default=True)
    is_active = models.BooleanField(_('Actif'), default=True)
    publisher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='courses_created', verbose_name=_('Instructeur'))
    estimated_duration = models.PositiveIntegerField(_('Durée estimée (heures)'), null=True, blank=True)
    skills = models.ManyToManyField(Technology, blank=True, related_name='courses', verbose_name=_('Compétence'))

    class Meta:
        verbose_name = _('Cours')
        verbose_name_plural = _('Cours')
        ordering = ['title']
        indexes = [models.Index(fields=['level', 'is_free', 'is_active']), models.Index(fields=['created_at']), ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.estimated_duration and self.estimated_duration <= 0:
            raise ValidationError({'estimated_duration': _('La durée doit être positive')})

    @property
    def total_modules(self):
        return self.modules.count()

    @property
    def total_contents(self):
        return Content.objects.filter(module__course=self).count()

    @property
    def total_quizzes(self):
        return Quiz.objects.filter(module__course=self).count()


class Module(LearningModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules', verbose_name=_('Cours'))
    title = models.CharField(_('Titre'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    order = models.PositiveIntegerField(_('Ordre'), default=0)
    is_active = models.BooleanField(_('Actif'), default=True)

    class Meta:
        verbose_name = _('Module')
        verbose_name_plural = _('Modules')
        ordering = ['course', 'order', 'title']
        indexes = [models.Index(fields=['course', 'order']), models.Index(fields=['is_active']), ]

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.order:
            last_module = Module.objects.filter(course=self.course).order_by('-order').first()
            self.order = (last_module.order + 1) if last_module else 1
        super().save(*args, **kwargs)


class ContentType(models.TextChoices):
    VIDEO = 'video', _('Vidéo')
    PDF = 'pdf', _('Document PDF')
    TALK = 'talk', _('Conférence')
    EXTERNAL_RESOURCE = 'external', _('Ressource Externe')
    MARKDOWN = 'markdown', _('Markdown')
    AUDIO = 'audio', _('Audio')
    IMAGE = 'image', _('Image')


class Content(LearningModel):
    description = None
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='contents', verbose_name=_('Module'))
    title = models.CharField(_('Titre'), max_length=255)
    content_type = models.CharField(_('Type de contenu'), max_length=15, choices=ContentType.choices)
    resource_file = models.FileField(_('Fichier'), null=True, blank=True, upload_to='learning/contents/')
    resource_url = models.URLField(_('URL'), null=True, blank=True)
    content = models.TextField(_('Contenu'), null=True, blank=True)
    order = models.PositiveIntegerField(_('Ordre'), default=0)
    is_active = models.BooleanField(_('Actif'), default=True)
    duration_minutes = models.PositiveIntegerField(_('Durée (minutes)'), null=True, blank=True)

    class Meta:
        verbose_name = _('Contenu')
        verbose_name_plural = _('Contenus')
        ordering = ['module', 'order', 'title']
        indexes = [models.Index(fields=['module', 'order']), models.Index(fields=['content_type']),
                   models.Index(fields=['is_active']), ]

    def clean(self):
        """Validation avancée du contenu"""
        super().clean()
        errors = {}

        if self.content_type in [ContentType.VIDEO, ContentType.AUDIO]:
            if not self.resource_file and not self.resource_url:
                msg = _(f'Un fichier ou une URL est requis pour le type {self.get_content_type_display()}.')
                errors['resource_file'] = msg
                errors['resource_url'] = msg

        elif self.content_type == ContentType.PDF:
            if not self.resource_file:
                errors['resource_file'] = _('Un fichier PDF est requis.')

        elif self.content_type in [ContentType.TALK, ContentType.EXTERNAL_RESOURCE]:
            if not self.resource_url:
                errors['resource_url'] = _(f'Une URL est requise pour le type {self.get_content_type_display()}.')

        elif self.content_type == ContentType.MARKDOWN:
            if not self.content:
                errors['content'] = _('Le contenu markdown est requis.')

        elif self.content_type == ContentType.IMAGE:
            if not self.resource_file:
                errors['resource_file'] = _('Un fichier image est requis.')

        if self.duration_minutes and self.duration_minutes <= 0:
            errors['duration_minutes'] = _('La durée doit être positive.')

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.order:
            last_content = Content.objects.filter(module=self.module).order_by('-order').first()
            self.order = (last_content.order + 1) if last_content else 1

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.module.title} - {self.title}"


class Quiz(LearningModel):
    module = models.OneToOneField(Module, null=True, on_delete=models.CASCADE, related_name='quiz',
                                  verbose_name=_('Module'))
    title = models.CharField(_('Titre'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    passing_score = models.PositiveIntegerField(_('Score de passage (%)'), default=70)
    time_limit_minutes = models.PositiveIntegerField(_('Limite de temps (minutes)'), null=True, blank=True)
    max_attempts = models.PositiveIntegerField(_('Nombre maximum de tentatives'), default=3)
    is_active = models.BooleanField(_('Actif'), default=True)
    randomize_questions = models.BooleanField(_('Questions aléatoires'), default=False)

    class Meta:
        verbose_name = _('Quiz')
        verbose_name_plural = _('Quiz')
        ordering = ['module', 'title']
        indexes = [models.Index(fields=['is_active']), ]

    def clean(self):
        super().clean()
        errors = {}

        if self.passing_score < 0 or self.passing_score > 100:
            errors['passing_score'] = _('Le score doit être entre 0 et 100.')

        if self.time_limit_minutes and self.time_limit_minutes <= 0:
            errors['time_limit_minutes'] = _('La limite de temps doit être positive.')

        if self.max_attempts < 0:
            errors['max_attempts'] = _('Le nombre de tentatives ne peut pas être négatif.')

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.module.title} - {self.title}"

    @property
    def questions_count(self):
        return self.questions.count()


class QuizQuestion(LearningModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions', verbose_name=_('Quiz'))
    title = models.CharField(_('Question'), max_length=500)
    description = models.TextField(_('Description'), blank=True)
    explanation = models.TextField(_('Explication'), blank=True)
    order = models.PositiveIntegerField(_('Ordre'), default=0)
    points = models.PositiveIntegerField(_('Points'), default=1)
    is_active = models.BooleanField(_('Active'), default=True)

    class Meta:
        verbose_name = _('Question de Quiz')
        verbose_name_plural = _('Questions de Quiz')
        ordering = ['quiz', 'order', 'id']
        indexes = [models.Index(fields=['quiz', 'order']), models.Index(fields=['is_active']), ]

    def save(self, *args, **kwargs):
        if not self.order:
            last_question = QuizQuestion.objects.filter(quiz=self.quiz).order_by('-order').first()
            self.order = (last_question.order + 1) if last_question else 1
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.points <= 0:
            raise ValidationError({'points': _('Les points doivent être positifs.')})

    def __str__(self):
        return self.title


class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='choices',
                                 verbose_name=_('Question'))
    text = models.CharField(_('Texte'), max_length=500)
    is_correct = models.BooleanField(_('Réponse correcte'), default=False)
    order = models.PositiveIntegerField(_('Ordre'), default=0)

    class Meta:
        verbose_name = _('Choix de réponse')
        verbose_name_plural = _('Choix de réponses')
        ordering = ['question', 'order', 'id']
        indexes = [models.Index(fields=['question', 'order']), models.Index(fields=['is_correct']), ]

    def save(self, *args, **kwargs):
        if not self.order:
            last_choice = QuizChoice.objects.filter(question=self.question).order_by('-order').first()
            self.order = (last_choice.order + 1) if last_choice else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.text


class QuizResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Utilisateur'))
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, verbose_name=_('Quiz'))
    started_at = models.DateTimeField(_('Commencé le'), auto_now_add=True)
    submitted_at = models.DateTimeField(_('Soumis le'), null=True, blank=True)
    score = models.FloatField(_('Score'), default=0)
    total_points = models.PositiveIntegerField(_('Points totaux'), default=0)
    obtained_points = models.PositiveIntegerField(_('Points obtenus'), default=0)
    is_passed = models.BooleanField(_('Réussi'), default=False)
    attempt_number = models.PositiveIntegerField(_('Numéro de tentative'), default=1)
    time_taken_seconds = models.PositiveIntegerField(_('Temps pris (secondes)'), null=True, blank=True)

    class Meta:
        verbose_name = _('Résultat de Quiz')
        verbose_name_plural = _('Résultats de Quiz')
        ordering = ['-started_at']
        indexes = [models.Index(fields=['user', 'quiz']), models.Index(fields=['is_passed']),
                   models.Index(fields=['started_at']), ]

    def save(self, *args, **kwargs):
        if self.submitted_at:
            if not self.time_taken_seconds:
                time_diff = self.submitted_at - self.started_at
                self.time_taken_seconds = int(time_diff.total_seconds())

            if self.total_points > 0:
                self.score = (self.obtained_points / self.total_points) * 100

            self.is_passed = self.score >= self.quiz.passing_score

        # Auto-increment attempt number
        if not self.attempt_number:
            last_attempt = QuizResult.objects.filter(user=self.user, quiz=self.quiz).order_by('-attempt_number').first()
            self.attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} - {self.score}%"

    @property
    def duration_formatted(self):
        if self.time_taken_seconds:
            minutes = self.time_taken_seconds // 60
            seconds = self.time_taken_seconds % 60
            return f"{minutes}m {seconds}s"
        return "N/A"


class QuizAnswer(models.Model):
    result = models.ForeignKey(QuizResult, on_delete=models.CASCADE, related_name='answers', verbose_name=_('Résultat'))
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, verbose_name=_('Question'))
    selected_choices = models.ManyToManyField(QuizChoice, verbose_name=_('Choix sélectionnés'), blank=True)
    is_correct = models.BooleanField(_('Correct'), default=False)
    points_earned = models.PositiveIntegerField(_('Points gagnés'), default=0)

    class Meta:
        verbose_name = _('Réponse de Quiz')
        verbose_name_plural = _('Réponses de Quiz')
        unique_together = ('result', 'question')
        indexes = [models.Index(fields=['result', 'question']), models.Index(fields=['is_correct']), ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.pk:
            correct_choices = self.question.choices.filter(is_correct=True)
            selected_choices = self.selected_choices.all()

            is_correct = (set(correct_choices) == set(
                selected_choices.filter(is_correct=True)) and not selected_choices.filter(is_correct=False).exists())

            if is_correct != self.is_correct:
                self.is_correct = is_correct
                self.points_earned = self.question.points if is_correct else 0
                QuizAnswer.objects.filter(pk=self.pk).update(is_correct=self.is_correct,
                                                             points_earned=self.points_earned)

    def __str__(self):
        return f"{self.result.user.username} - {self.question.title[:50]} - {'✓' if self.is_correct else '✗'}"


class Progress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Utilisateur'))
    content = models.ForeignKey(Content, on_delete=models.CASCADE, verbose_name=_('Contenu'))
    is_completed = models.BooleanField(_('Terminé'), default=False)
    completed_at = models.DateTimeField(_('Terminé le'), null=True, blank=True)
    started_at = models.DateTimeField(_('Commencé le'), auto_now_add=True)
    last_accessed = models.DateTimeField(_('Dernier accès'), auto_now=True)
    time_spent_seconds = models.PositiveIntegerField(_('Temps passé (secondes)'), default=0)

    class Meta:
        verbose_name = _('Progrès')
        verbose_name_plural = _('Progrès')
        unique_together = ('user', 'content')
        ordering = ['-last_accessed']
        indexes = [models.Index(fields=['user', 'content']), models.Index(fields=['is_completed']),
                   models.Index(fields=['last_accessed']), ]

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.is_completed:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.user.username} - {self.content.title}"


class Certificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Utilisateur'))
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name=_('Cours'))
    issued_at = models.DateTimeField(_('Émis le'), auto_now_add=True)
    file = models.FileField(_('Fichier'), upload_to='certificates/', null=True, blank=True)
    certificate_number = models.CharField(_('Numéro de certificat'), max_length=50, unique=True, null=True, blank=True)
    is_valid = models.BooleanField(_('Valide'), default=True)

    class Meta:
        verbose_name = _('Certificat')
        verbose_name_plural = _('Certificats')
        unique_together = ('user', 'course')
        ordering = ['-issued_at']
        indexes = [models.Index(fields=['certificate_number']), models.Index(fields=['is_valid']),
                   models.Index(fields=['issued_at']), ]

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            import uuid
            self.certificate_number = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Certif: {self.user.username} - {self.course.title}"
