import secrets

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from core.models import BaseModel
from evaluations.models import Answer
from questions.models import Question


class ExperienceLevel(models.TextChoices):
    JUNIOR = 'junior', _('Junior (0-2 ans d\'expérience)')
    INTERMEDIATE = 'intermediate', _('Intermédiaire (3-5 ans d\'expérience')
    SENIOR = 'senior', _('Senior (5+ ans d\'expérience)')


class Organization(models.Model):
    class Meta:
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')

    name = models.CharField(_('Nom'), max_length=255)
    description = models.TextField(_('Description'), blank=True, null=True)
    account = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization',
                                   verbose_name=_('Compte'))
    logo = models.ImageField(_('Logo'), upload_to='companies/logos/', blank=True, null=True)
    website = models.URLField(_('Site web'), blank=True)
    address = models.CharField(_('Adresse'), max_length=255, blank=True)
    city = models.CharField(_('Ville'), max_length=100, blank=True)
    country = models.CharField(_('Pays'), max_length=100, blank=True)
    created_at = models.DateTimeField(_('Date de création'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Date de mise à jour'), auto_now=True)

    def __str__(self):
        return self.name


class Candidate(models.Model):
    """Représente un candidat externe qui n'est pas un utilisateur du système"""

    class Meta:
        verbose_name = _('Candidat')
        verbose_name_plural = _('Candidats')

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='candidates')
    email = models.EmailField(_('Email'))
    full_name = models.CharField(_('Nom complet'), max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class OrgEvaluation(BaseModel):
    class QuestionOrder(models.IntegerChoices):
        RANDOM = 1, _('Aléatoire')
        ADDED = 2, _('Ordre d\'ajout')
        SKILL = 3, _('Par compétence')

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='evaluations',
                                     verbose_name=_('Organisation'))
    title = models.CharField(_('Titre'), max_length=255)
    description = models.TextField(_('Description'), blank=True, null=True)
    questions_order = models.IntegerField(_('Ordre des questions'), choices=QuestionOrder.choices,
                                          default=QuestionOrder.RANDOM)
    archived = models.BooleanField(_('Archivé'), default=False)

    slug = models.SlugField(max_length=255, unique=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['slug'])]
        verbose_name = _('Organisation Evaluation')
        verbose_name_plural = _('Organisation Evaluations')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def is_ready(self):
        """Une évaluation est prête si elle a au moins 5 questions"""
        return self.questions.count() >= 5

    @property
    def max_score(self):
        """Retourne le score maximum possible pour cette évaluation"""
        return sum(q.weight for q in self.questions.all())


class OrgQuestion(BaseModel):
    """Question créée ou copiée par une organisation"""

    class Meta:
        verbose_name = _('Question d\'organisation')
        verbose_name_plural = _('Questions d\'organisation')
        ordering = ['-created_at']
        indexes = [models.Index(fields=['difficulty']), ]

    evaluation = models.ForeignKey(OrgEvaluation, on_delete=models.CASCADE, related_name='questions',
                                   verbose_name=_('Évaluation'))
    technology = models.ForeignKey('core.Technology', on_delete=models.CASCADE, related_name='org_questions',
                                   verbose_name=_('Technologie'), null=True, blank=True)

    original_question = models.ForeignKey(Question, on_delete=models.SET_NULL, related_name='org_copies', null=True,
                                          blank=True, verbose_name=_('Question originale'))
    text = models.TextField(_('Titre'))
    explanation = models.TextField(
        _('Explication'), help_text=_('Explication de la réponse'))
    difficulty = models.CharField(max_length=10, choices=Question.Difficulty.choices, verbose_name=_('Difficulté'),
                                  default=Question.Difficulty.MEDIUM)
    duration = models.IntegerField(_('Durée'), default=100, help_text=_('Durée en secondes'),
                                   validators=[MinValueValidator(20), MaxValueValidator(200)])

    def __str__(self):
        return self.text[:50]

    @property
    def weight(self):
        return Question.DIFFICULTY_WEIGHTS.get(self.difficulty, 0)


class OrgChoice(BaseModel):
    """Choix pour une question d'organisation"""

    class Meta:
        verbose_name = _('Choix d\'organisation')
        verbose_name_plural = _('Choix d\'organisation')
        indexes = [models.Index(fields=['question', 'is_correct']), ]

    question = models.ForeignKey(
        OrgQuestion, on_delete=models.CASCADE, related_name='choices')
    text = models.TextField(_('Texte'))
    is_correct = models.BooleanField(_('Est correct'), default=False)

    def __str__(self):
        return f"{self.text[:30]}... - {'Correct' if self.is_correct else 'Incorrect'}"


class OrgSubmissionAttempt(BaseModel):
    """Tentative de soumission pour une évaluation d'organisation"""

    class Meta:
        verbose_name = _('Tentative de soumission d\'organisation')
        verbose_name_plural = _('Tentatives de soumission d\'organisation')
        indexes = [models.Index(fields=['started_at']), ]
        unique_together = ('evaluation', 'candidate')

    evaluation = models.ForeignKey(OrgEvaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
                                   related_name='attempts')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, verbose_name=_('Candidat'),
                                  related_name='attempts')
    submission = models.OneToOneField('OrgSubmission', on_delete=models.CASCADE, verbose_name=_('Soumission'),
                                      related_name='attempt', blank=True, null=True)
    started_at = models.DateTimeField(_('Commencé le'), auto_now_add=True)
    ended_at = models.DateTimeField(_('Terminé le'), blank=True, null=True)
    questions = models.ManyToManyField(OrgQuestion, verbose_name=_(
        'Questions'), blank=True, related_name='attempts')
    is_completed = models.BooleanField(_('Complété'), default=False)

    def __str__(self):
        return f'{self.candidate} - {self.evaluation} - {self.started_at}'


class OrgSubmission(BaseModel):
    """Soumission d'une évaluation d'organisation"""
    score = models.FloatField(_('Résultat'), blank=True, null=True)
    submitted_at = models.DateTimeField(_('Soumis le'), auto_now_add=True)

    class Meta:
        verbose_name = _('Soumission d\'organisation')
        verbose_name_plural = _('Soumissions d\'organisation')
        ordering = ['-submitted_at']
        indexes = [models.Index(fields=['score']), ]

    def __str__(self):
        return f'{self.score} - {self.submitted_at}'


class OrgAnswer(BaseModel):
    """Réponse à une question d'organisation"""

    attempt = models.ForeignKey(OrgSubmissionAttempt, on_delete=models.CASCADE,
                                verbose_name=_('Tentative de soumission'), related_name='answers')
    question = models.ForeignKey(OrgQuestion, on_delete=models.CASCADE, verbose_name=_('Question'),
                                 related_name='answers')
    selected_choices = models.ManyToManyField(OrgChoice, verbose_name=_('Choix sélectionnés'), blank=True,
                                              related_name='answers')
    is_correct = models.BooleanField(_('Correcte'), blank=True, null=True)
    answered_at = models.DateTimeField(_('Répondu le'), auto_now_add=True)
    delta_time = models.PositiveSmallIntegerField(_('Durée'))
    status = models.CharField(_('Statut'), choices=Answer.Status.choices,
                              default=Answer.Status.PENDING, max_length=20)
    score = models.IntegerField(_('Résultat'), default=0)

    class Meta:
        verbose_name = _('Réponse d\'organisation')
        verbose_name_plural = _('Réponses d\'organisation')
        unique_together = ('attempt', 'question')
        indexes = [models.Index(fields=['status']),
                   models.Index(fields=['is_correct'])]

    def __str__(self):
        return f'{self.attempt} - {self.question} - {self.answered_at} - {"Correct" if self.is_correct else "Incorrect"}'


class EvaluationInvitation(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente')
        ACCEPTED = 'accepted', _('Accepté')
        DECLINED = 'declined', _('Refusé')
        EXPIRED = 'expired', _('Expirée')

    evaluation = models.ForeignKey(OrgEvaluation, on_delete=models.CASCADE, verbose_name=_('Évaluation'),
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
