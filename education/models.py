from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from questions.models import Category, Question


class School(models.Model):
    name = models.CharField('Nom de l’établissement', max_length=255)
    code = models.SlugField('Code', max_length=80, unique=True)
    is_active = models.BooleanField('Active', default=True)
    created_at = models.DateTimeField('Créée le', auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Établissement'
        verbose_name_plural = 'Établissements'

    def __str__(self):
        return self.name


class SchoolStaff(models.Model):
    class Role(models.TextChoices):
        MANAGER = 'MANAGER', 'Responsable d’établissement'
        TEACHER = 'TEACHER', 'Enseignant'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='school_staff')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='staff')
    role = models.CharField('Rôle', max_length=20, choices=Role.choices)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Personnel scolaire'
        verbose_name_plural = 'Personnel scolaire'
        constraints = [
            models.UniqueConstraint(fields=['user', 'school'], name='unique_school_staff'),
        ]

    def __str__(self):
        return f'{self.user.get_full_name()} - {self.school}'


class AcademicClass(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='classes')
    name = models.CharField('Nom de la classe', max_length=120)
    level = models.CharField('Niveau', max_length=120)
    academic_year = models.CharField('Année scolaire', max_length=20)
    teachers = models.ManyToManyField(SchoolStaff, blank=True, related_name='classes_taught')

    class Meta:
        ordering = ['school', 'level', 'name']
        verbose_name = 'Classe'
        verbose_name_plural = 'Classes'
        constraints = [
            models.UniqueConstraint(fields=['school', 'name', 'academic_year'], name='unique_school_class_year'),
        ]

    def __str__(self):
        return f'{self.name} ({self.academic_year})'


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students')
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name='students')
    student_number = models.CharField('Matricule', max_length=80, blank=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        ordering = ['academic_class', 'user__last_name', 'user__first_name']
        verbose_name = 'Élève / étudiant'
        verbose_name_plural = 'Élèves / étudiants'

    def __str__(self):
        return f'{self.user.get_full_name()} - {self.academic_class}'


class Subject(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField('Matière', max_length=160)
    code = models.CharField('Code', max_length=40, blank=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_school_subject'),
        ]

    def __str__(self):
        return self.name


class TeacherQuestion(models.Model):
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'MCQ', 'Choix multiple'
        UNIQUE_CHOICE = 'UCQ', 'Choix unique'
        OPEN_ANSWER = 'OA', 'Réponse ouverte'

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teacher_questions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_questions')
    title = models.CharField('Titre', max_length=255)
    description = models.TextField('Description', blank=True)
    question_type = models.CharField('Type de question', choices=QuestionType.choices, default=QuestionType.UNIQUE_CHOICE, max_length=3)
    points = models.PositiveIntegerField('Points par défaut', default=1, validators=[MinValueValidator(1)])
    is_active = models.BooleanField('Active', default=True)
    created_at = models.DateTimeField('Créée le', auto_now_add=True)
    updated_at = models.DateTimeField('Modifiée le', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Question enseignant'
        verbose_name_plural = 'Questions enseignants'

    def __str__(self):
        return f'{self.title} ({self.subject.name})'

    @property
    def is_multiple_choice(self):
        return self.question_type == self.QuestionType.MULTIPLE_CHOICE

    @property
    def is_unique_choice(self):
        return self.question_type == self.QuestionType.UNIQUE_CHOICE

    @property
    def is_open_answer(self):
        return self.question_type == self.QuestionType.OPEN_ANSWER


class TeacherChoice(models.Model):
    teacher_question = models.ForeignKey(TeacherQuestion, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField('Texte', max_length=255)
    is_correct = models.BooleanField('Correcte', default=False)
    position = models.PositiveIntegerField('Position', default=1)

    class Meta:
        ordering = ['position']
        verbose_name = 'Choix enseignant'
        verbose_name_plural = 'Choix enseignants'

    def __str__(self):
        return self.text


class Exam(models.Model):
    class GradingScale(models.IntegerChoices):
        OUT_OF_20 = 20, 'Sur 20'
        OUT_OF_100 = 100, 'Sur 100'

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='exams')
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name='exams')
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='exams')
    title = models.CharField('Titre', max_length=255)
    instructions = models.TextField('Consignes', blank=True)
    starts_at = models.DateTimeField('Début')
    ends_at = models.DateTimeField('Fin')
    duration_minutes = models.PositiveIntegerField('Durée (minutes)', validators=[MinValueValidator(1)])
    max_attempts = models.PositiveIntegerField('Tentatives autorisées', default=1, validators=[MinValueValidator(1)])
    grading_scale = models.PositiveSmallIntegerField('Barème', choices=GradingScale.choices, default=20)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='school_exams_created')
    is_published = models.BooleanField('Publié', default=False)
    results_published = models.BooleanField('Résultats publiés', default=False)
    created_at = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        ordering = ['-starts_at']
        verbose_name = 'Épreuve scolaire'
        verbose_name_plural = 'Épreuves scolaires'

    def __str__(self):
        return f'{self.title} - {self.academic_class}'

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.academic_class_id and self.school_id and self.academic_class.school_id != self.school_id:
            errors['academic_class'] = 'La classe doit appartenir au même établissement que l’épreuve.'
        if self.subject_id and self.school_id and self.subject.school_id != self.school_id:
            errors['subject'] = 'La matière doit appartenir au même établissement que l’épreuve.'
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors['ends_at'] = 'La fin doit être postérieure au début.'
        if errors:
            raise ValidationError(errors)


class ExamQuestion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_questions')
    teacher_question = models.ForeignKey(TeacherQuestion, on_delete=models.PROTECT, related_name='exam_questions', null=True, blank=True)
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name='school_exam_questions', null=True, blank=True)
    points = models.PositiveIntegerField('Points', default=1, validators=[MinValueValidator(1)])
    position = models.PositiveIntegerField('Position', default=1)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['exam', 'teacher_question'], name='unique_exam_teacher_question'),
            models.UniqueConstraint(fields=['exam', 'question'], name='unique_exam_question'),
        ]

    def __str__(self):
        return f'{self.exam} - question {self.position}'

    @property
    def effective_question(self):
        return self.teacher_question if self.teacher_question else self.question


class ExamAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        SUBMITTED = 'SUBMITTED', 'Soumise'
        REVIEW = 'REVIEW', 'À corriger'
        CORRECTED = 'CORRECTED', 'Corrigée'

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attempts')
    attempt_number = models.PositiveIntegerField('Numéro de tentative')
    started_at = models.DateTimeField('Commencée le', auto_now_add=True)
    expires_at = models.DateTimeField('Expire le')
    submitted_at = models.DateTimeField('Soumise le', null=True, blank=True)
    status = models.CharField('Statut', max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    score = models.FloatField('Note', null=True, blank=True)
    started_ip = models.GenericIPAddressField('IP de début', null=True, blank=True)
    submitted_ip = models.GenericIPAddressField('IP de remise', null=True, blank=True)
    user_agent = models.TextField('Navigateur', blank=True)
    integrity_events = models.JSONField('Événements d’intégrité', default=list, blank=True)
    fraud_flag = models.BooleanField('Signalement à vérifier', default=False)
    fraud_reason = models.TextField('Motif du signalement', blank=True)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(fields=['exam', 'student', 'attempt_number'], name='unique_exam_student_attempt'),
        ]

    def __str__(self):
        return f'{self.student} - {self.exam} - tentative {self.attempt_number}'


class ExamAnswer(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    exam_question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='student_answers')
    text = models.TextField('Réponse', blank=True)
    selected_choices = models.ManyToManyField('questions.Choice', blank=True, related_name='school_exam_answers')
    selected_teacher_choices = models.ManyToManyField(TeacherChoice, blank=True, related_name='exam_answers')
    is_correct = models.BooleanField('Correcte', null=True, blank=True)
    points_awarded = models.FloatField('Points obtenus', default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['attempt', 'exam_question'], name='unique_attempt_exam_question'),
        ]

    def __str__(self):
        return f'{self.attempt} - {self.exam_question}'
