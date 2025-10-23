import secrets

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TitleSlugDescriptionModel

from apps.core.models import BaseModel, Profession, delete_old_image
from apps.questions.models import Question, Choice


def _upload_to(instance, filename):
    """Détermine le chemin de stockage des images d'évaluations"""
    return f'evaluations/{slugify(instance.title)}/{filename}'


class EvaluationType(models.TextChoices):
    COMPETITION = 'competition', _('Competition')
    TECHNICAL = 'technical', _('Technique')
    LOGICAL = 'logical', _('Logique')
    PERSONALITY = 'personality', _('Personnalité')


class QuestionOrder(models.IntegerChoices):
    RANDOM = 1, _('Aléatoire')
    ADDED = 2, _('Ordre d\'ajout')
    SKILL = 3, _('Par compétence')


class ExperienceLevel(models.TextChoices):
    JUNIOR = 'junior', _('Junior (0-2 ans d\'expérience)')
    INTERMEDIATE = 'intermediate', _('Intermédiaire (3-5 ans d\'expérience')
    SENIOR = 'senior', _('Senior (5+ ans d\'expérience)')


class Evaluation(BaseModel, TitleSlugDescriptionModel):
    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', _('Débutant 0- 2 ans d\'expérience')
        INTERMEDIATE = 'intermediate', _('Intermédiaire 3-5 ans d\'expérience')
        EXPERT = 'expert', _('Expert 5+ ans d\'expérience')

    title = models.CharField(_('Title'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    image = models.ImageField(_('Image'), upload_to=_upload_to, blank=True, null=True)

    technology = models.ForeignKey('core.Technology', related_name='evaluations', verbose_name=_('Technologie'),
                                   on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    technologies = models.ManyToManyField('core.Technology', related_name='evaluation_technologies', 
                                          verbose_name=_('Technologies'), blank=True)
    profession = models.ForeignKey(Profession, on_delete=models.CASCADE, related_name='evaluations',
                                   verbose_name=_('Profession'), null=True, blank=True, db_index=True)
    publisher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('Créateur'),
                                  related_name='evaluations', db_index=True)

    difficulty = models.CharField(_('Difficulty'), choices=Difficulty.choices, default=Difficulty.BEGINNER,
                                  max_length=20, db_index=True)
    evaluation_type = models.CharField(_('Type'), choices=EvaluationType.choices, default=EvaluationType.TECHNICAL,
                                       max_length=20, db_index=True)

    questions_order = models.IntegerField(_('Ordre des questions'), choices=QuestionOrder.choices,
                                          default=QuestionOrder.ADDED)
    archived = models.BooleanField(_('Archivé'), default=False, db_index=True)
    is_active = models.BooleanField(_('Actif'), default=True, db_index=True, help_text=_('Indique si l\'évaluation est publiée et visible'))

    questions = models.ManyToManyField(Question, verbose_name=_('Questions'), blank=True, related_name='evaluations')

    class Meta:
        verbose_name = _('Evaluation')
        verbose_name_plural = _('Evaluations')
        ordering = ['-created_at']
        indexes = [models.Index(fields=['slug']), models.Index(fields=['difficulty']),
                   models.Index(fields=['archived']), ]

    def __str__(self):
        return self.title

    @property
    def is_constructed(self):
        """Détermine si l'évaluation a assez de questions publiées"""
        min_questions = 5 if hasattr(self.publisher, 'organization') else 20
        return self.questions.filter(status=Question.Status.PUBLISHED).count() >= min_questions

    @property
    def max_score(self):
        """Retourne le score maximum possible pour cette évaluation"""
        return sum(q.weight for q in self.questions.filter(status=Question.Status.PUBLISHED))


class Candidate(BaseModel):
    """Représente un candidat externe qui n'est pas un utilisateur du système"""

    class Meta:
        verbose_name = _('Candidat')
        verbose_name_plural = _('Candidats')

    email = models.EmailField(_('Email'))
    full_name = models.CharField(_('Nom complet'), max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidates',
                              verbose_name=_('Créateur'))

    def __str__(self):
        return self.full_name


class Participant(models.Model):
    """Classe intermédiaire pour représenter un participant (User ou Candidate)"""

    class Type(models.TextChoices):
        USER = 'user', _('Utilisateur')
        CANDIDATE = 'candidate', _('Candidat')

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('Utilisateur'),
                                blank=True, null=True)
    candidate = models.OneToOneField(Candidate, on_delete=models.CASCADE, verbose_name=_('Candidat'), blank=True,
                                     null=True)
    type = models.CharField(_('Type'), choices=Type.choices, max_length=20, db_index=True)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        verbose_name = _('Participant')
        verbose_name_plural = _('Participants')
        constraints = [
            models.CheckConstraint(
                check=models.Q(user__isnull=False, candidate__isnull=True) |
                      models.Q(user__isnull=True, candidate__isnull=False),
                name='participant_exclusive_user_or_candidate'
            )
        ]

    def __str__(self):
        return str(self.user) if self.user else str(self.candidate)

    @property
    def email(self):
        return self.user.email if self.user else self.candidate.email

    @property
    def full_name(self):
        return self.user.get_full_name() if self.user else self.candidate.full_name

    @property
    def real_id(self):
        return self.user.id if self.user else self.candidate.id


class SubmissionAttempt(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                   related_name='attempts', db_index=True)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, verbose_name=_('Participant'),
                                    related_name='attempts', db_index=True)

    submission = models.OneToOneField('Submission', on_delete=models.CASCADE, verbose_name=_('Soumission'),
                                      related_name='attempt', blank=True, null=True)
    started_at = models.DateTimeField(_('Commencé le'), auto_now_add=True, db_index=True)
    ended_at = models.DateTimeField(_('Terminé le'), blank=True, null=True)

    questions = models.ManyToManyField(Question, verbose_name=_('Questions'), blank=True, related_name='attempts')

    is_completed = models.BooleanField(_('Complété'), default=False)
    corrected = models.BooleanField(_('Corrigée'), default=False)

    class Meta:
        verbose_name = _('Tentative de soumission')
        verbose_name_plural = _('Tentatives de soumission')
        indexes = [
            models.Index(fields=['started_at']),
            models.Index(fields=['participant', 'evaluation']),
            models.Index(fields=['is_completed']),
        ]
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.participant} - {self.evaluation} - {self.started_at}'

    @property
    def is_finished(self):
        return self.ended_at is not None and self.submission is not None


class Submission(models.Model):
    score = models.FloatField(_('Résultat'), blank=True, null=True)
    submitted_at = models.DateTimeField(_('Soumis le'), auto_now_add=True, db_index=True)

    personality_detail = models.TextField(_('Personnalité'), blank=True, null=True)

    class Meta:
        verbose_name = _('Soumission')
        verbose_name_plural = _('Soumissions')
        ordering = ['-submitted_at']
        indexes = [models.Index(fields=['score']), ]

    def __str__(self):
        return f'{self.score} - {self.submitted_at}'

    @property
    def score_percent(self):
        return round((self.score / self.attempt.evaluation.max_score) * 100, 2)


class Answer(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente de correction')
        DISCARDED = 'discarded', _('Abandonnée')
        TIMEOUT = 'timeout', _('Timeout')
        PARTIAL = 'partial', _('Correct partiellement')
        CORRECT = 'correct', _('Correcte')
        INCORRECT = 'incorrect', _('Incorrecte')

    attempt = models.ForeignKey(SubmissionAttempt, on_delete=models.CASCADE, verbose_name=_('Tentative de soumission'),
                                related_name='answers', db_index=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name=_('Question'), related_name='answers',
                                 db_index=True)
    selected_choices = models.ManyToManyField(Choice, verbose_name=_('Choix sélectionnés'), blank=True,
                                              related_name='answers')
    is_correct = models.BooleanField(_('Correcte'), blank=True, null=True, db_index=True)
    answered_at = models.DateTimeField(_('Répondu le'), auto_now_add=True, db_index=True)
    delta_time = models.PositiveSmallIntegerField(_('Durée'), validators=[MaxValueValidator(200)])
    status = models.CharField(_('Statut'), choices=Status.choices, default=Status.PENDING, max_length=20, db_index=True)
    score = models.IntegerField(_('Résultat'), default=0)

    class Meta:
        verbose_name = _('Réponse')
        verbose_name_plural = _('Réponses')
        unique_together = ('attempt', 'question')
        indexes = [models.Index(fields=['status']), models.Index(fields=['is_correct'])]

    @property
    def corrected(self):
        return self.is_correct is not None

    def __str__(self):
        return f'{self.question}'


class Competition(models.Model):
    evaluation = models.OneToOneField(Evaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                      limit_choices_to={'evaluation_type': EvaluationType.COMPETITION},
                                      related_name='competition')

    started_at = models.DateTimeField(_('Commencé le'), blank=True, null=True)
    ended_at = models.DateTimeField(_('Terminé le'), blank=True, null=True)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        verbose_name = _('Competition')
        verbose_name_plural = _('Competitions')
        ordering = ['-created_at']


class EvaluationInvitation(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente')
        ACCEPTED = 'accepted', _('Accepté')
        DECLINED = 'declined', _('Refusé')
        EXPIRED = 'expired', _('Expirée')

    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                   related_name='invitations')
    candidate = models.OneToOneField(Candidate, on_delete=models.CASCADE, verbose_name=_('Candidat'),
                                     related_name='invitation')
    token = models.CharField(_('Token d\'invitation'),
                             max_length=64, unique=True)
    invited_at = models.DateTimeField(_('Invité le'), auto_now_add=True)
    expires_at = models.DateTimeField(_('Expire le'))
    status = models.CharField(
        _('Statut'), choices=Status.choices, default=Status.PENDING, max_length=20)

    class Meta:
        unique_together = ('evaluation', 'candidate')
        indexes = [models.Index(fields=['token']),
                   models.Index(fields=['status'])]
        ordering = ['-invited_at']

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """Vérifie si l'invitation est valide"""
        return self.status not in [self.Status.EXPIRED, self.Status.DECLINED] and self.expires_at > timezone.now()

    def __str__(self):
        return f'Invitation {self.token} - {self.evaluation.title} - {self.candidate.full_name} - {self.status}'


class SkillEvaluation(BaseModel):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='skill_evaluations',
                                   verbose_name=_('Évaluation'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skill_evaluations',
                             verbose_name=_('User'))


receiver([pre_save, pre_delete], sender=Evaluation)(delete_old_image)
