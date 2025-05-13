from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.timezone import now

from accounts.models import User
from questions.models import Question, Choice, Domain


class Settings(models.Model):
    default_challenge_duration = models.DurationField("Durée par défaut d'un challenge", default=timedelta(hours=1))
    beginner_challenge_duration = models.DurationField("Durée d'un challenge pour les débutants",
                                                       default=timedelta(hours=1))
    intermediate_challenge_duration = models.DurationField("Durée d'un challenge pour les intermédiaires",
                                                           default=timedelta(hours=1))
    advanced_challenge_duration = models.DurationField("Durée d'un challenge pour les avancés",
                                                       default=timedelta(hours=1))
    is_database_already_populated = models.BooleanField('Base de données déjà peuplée', default=False)

    open_answer_question_count_per_tag = models.PositiveIntegerField('Nombre de réponses ouvertes par tag', default=5)
    multiple_choice_question_count_per_tag = models.PositiveIntegerField('Nombre de questions multiples choix par tag',
                                                                         default=3)
    unique_choice_question_count_per_tag = models.PositiveIntegerField('Nombre de questions choix unique par tag',
                                                                       default=2)

    class Meta:
        verbose_name = 'Paramètre'
        verbose_name_plural = 'Paramètres'

    def __str__(self):
        return 'Paramètres'


class Challenge(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, verbose_name='Domaine', related_name='challenges')
    title = models.CharField('Titre', max_length=255)
    description = models.TextField('Description', blank=True, null=True)
    duration = models.DurationField('Durée', blank=True, help_text='Durée en HH:MM:SS')
    slug = models.SlugField('Slug', max_length=255, blank=True, null=True)
    questions = models.ManyToManyField(Question, verbose_name='Questions', blank=True, related_name='challenges')
    is_logical = models.BooleanField('Test logique', default=False)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Challenge'
        verbose_name_plural = 'Challenges'

    def __str__(self):
        return self.domain.name + ' - ' + self.title

    def save(self, *args, **kwargs):
        if not self.duration:
            self.duration = Settings.objects.first().default_challenge_duration
        self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class SubmissionAttempt(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, verbose_name='Challenge',
                                  related_name='attempts')
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Utilisateur',
                                  related_name='attempts')
    submission = models.OneToOneField('Submission', on_delete=models.CASCADE, verbose_name='Soumission',
                                      related_name='attempt', blank=True, null=True)
    started_at = models.DateTimeField('Commencé le', auto_now_add=True)
    ended_at = models.DateTimeField('Terminé le', blank=True, null=True)

    class Meta:
        verbose_name = 'Tentative de soumission'
        verbose_name_plural = 'Tentatives de soumission'

    def __str__(self):
        return f'{self.candidate} - {self.challenge} - {self.started_at}'

    @property
    def is_finished(self):
        return self.ended_at is not None

    @property
    def performance_percent(self):
        if self.ended_at:
            return 100 - 100 * (
                    self.ended_at - self.started_at).total_seconds() / self.challenge.duration.total_seconds()
        else:
            return 0.0

    @property
    def performance(self):
        if self.ended_at:
            return timedelta(seconds=(self.ended_at - self.started_at).seconds)
        else:
            return None

    @property
    def remaining_time(self):
        return self.challenge.duration - (now() - self.started_at)


class Submission(models.Model):
    class CorrectionStatus(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        CORRECTED = 'CORRECTED', 'Corrigé'

    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, verbose_name='Challenge',
                                  related_name='submissions')
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Utilisateur',
                                  related_name='submissions')
    result = models.FloatField('Résultat', blank=True, null=True)
    status = models.CharField('Statut', choices=CorrectionStatus.choices, default=CorrectionStatus.PENDING,
                              max_length=20)
    submitted_at = models.DateTimeField('Soumis le', auto_now_add=True)

    class Meta:
        verbose_name = 'Soumission'
        verbose_name_plural = 'Soumissions'
        ordering = ['-submitted_at']

    @property
    def is_corrected(self):
        return self.status == self.CorrectionStatus.CORRECTED

    @property
    def result_percent(self):
        return 100 * self.result

    @property
    def correct_count(self):
        return self.answers.filter(is_correct=True).count()

    def __str__(self):
        return f'{self.candidate} - {self.challenge} - {self.submitted_at}'


class Answer(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, verbose_name='Soumission',
                                   related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name='Question', related_name='answers')
    text = models.TextField('Réponse textuelle', blank=True, null=True)
    selected_choices = models.ManyToManyField(Choice, verbose_name='Choix sélectionnés', blank=True,
                                              related_name='submissions')
    is_correct = models.BooleanField('Correcte', blank=True, null=True)
    answered_at = models.DateTimeField('Répondu le', auto_now_add=True)

    class Meta:
        verbose_name = 'Réponse'
        verbose_name_plural = 'Réponses'

    @property
    def corrected(self):
        return self.is_correct is not None

    @property
    def average_score(self) -> float:
        if not self.corrected:
            return 0.0
        if self.question.is_open_answer:
            return 1 if bool(self.is_correct) else 0
        correct_choices = self.question.choices.filter(is_correct=True)
        selected_ids = [choice.id for choice in self.selected_choices.all()]
        correct_count = correct_choices.filter(id__in=selected_ids).count()
        return correct_count / correct_choices.count()

    def __str__(self):
        return f'{self.question} '


class APIUsage(models.Model):
    date = models.DateField('Date', default=now)
    count = models.IntegerField('Nombre de requêtes', default=0)

    class Meta:
        verbose_name = 'Utilisation GEMINI API'
        verbose_name_plural = 'Utilisation GEMINI API'

    def __str__(self):
        return f'{self.date} - {self.count}'

    @property
    def limit_reached(self):
        return self.count > 1500


class PersonalityChallenge(models.Model):
    title = models.CharField('Titre', max_length=255)
    description = models.TextField('Description', blank=True, null=True)
    slug = models.SlugField('Slug', max_length=255, blank=True, null=True)
    questions = models.ManyToManyField(Question, verbose_name='Questions', blank=True,
                                       related_name='personality_challenges')
    personality_detail = models.TextField('Détails de la personne', blank=True, null=True)
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Utilisateur',
                                  related_name='personality_challenges')
    is_passed = models.BooleanField('Passé', default=False)
    corrected = models.BooleanField('Corrigé', default=False)

    class Meta:
        verbose_name = 'Challenge de Personnalité'
        verbose_name_plural = 'Challenges de Personnalité'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class PersonalityAnswer(models.Model):
    submission = models.ForeignKey(PersonalityChallenge, on_delete=models.CASCADE, verbose_name='Soumission',
                                   related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name='Question',
                                 related_name='personality_answers')
    text = models.TextField('Réponse textuelle', blank=True, null=True)
    selected_choices = models.ManyToManyField(Choice, verbose_name='Choix sélectionnés', blank=True,
                                              related_name='personality_submissions')
    answered_at = models.DateTimeField('Répondu le', auto_now_add=True)

    class Meta:
        verbose_name = 'Réponse de Personnalité'
        verbose_name_plural = 'Réponses de personnalités'
