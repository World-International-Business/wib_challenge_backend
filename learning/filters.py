from django.contrib.auth import get_user_model
from django_filters import rest_framework as filters

from .models import (
    Course, Module, Content, Quiz, QuizQuestion, QuizChoice, QuizResult,
    Progress, Certificate, SkillLevel, ContentType
)

User = get_user_model()


class CourseFilter(filters.FilterSet):
    """Filtre pour les cours"""
    title = filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        help_text='Filtrer par titre (recherche partielle)'
    )

    level = filters.ChoiceFilter(
        choices=SkillLevel.choices,
        field_name='level',
        help_text='Filtrer par niveau de compétence'
    )

    is_free = filters.BooleanFilter(
        field_name='is_free',
        help_text='Filtrer par cours gratuits ou payants'
    )

    class Meta:
        model = Course
        fields = ['title', 'level', 'is_free']


class ModuleFilter(filters.FilterSet):
    """Filtre pour les modules"""
    course = filters.ModelChoiceFilter(
        queryset=Course.objects.all(),
        field_name='course',
        help_text='Filtrer par cours'
    )

    course_id = filters.NumberFilter(
        field_name='course__id',
        help_text='Filtrer par ID du cours'
    )

    title = filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        help_text='Filtrer par titre (recherche partielle)'
    )

    class Meta:
        model = Module
        fields = ['course', 'course_id', 'title']


class ContentFilter(filters.FilterSet):
    """Filtre pour les contenus"""
    module = filters.ModelChoiceFilter(
        queryset=Module.objects.all(),
        field_name='module',
        help_text='Filtrer par module'
    )

    module_id = filters.NumberFilter(
        field_name='module__id',
        help_text='Filtrer par ID du module'
    )

    course = filters.ModelChoiceFilter(
        queryset=Course.objects.all(),
        field_name='module__course',
        help_text='Filtrer par cours'
    )

    course_id = filters.NumberFilter(
        field_name='module__course__id',
        help_text='Filtrer par ID du cours'
    )

    title = filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        help_text='Filtrer par titre (recherche partielle)'
    )

    content_type = filters.ChoiceFilter(
        choices=ContentType.choices,
        field_name='content_type',
        help_text='Filtrer par type de contenu'
    )

    class Meta:
        model = Content
        fields = ['module', 'module_id', 'course', 'course_id', 'title', 'content_type']


class QuizFilter(filters.FilterSet):
    """Filtre pour les quiz"""
    module = filters.ModelChoiceFilter(
        queryset=Module.objects.all(),
        field_name='module',
        help_text='Filtrer par module'
    )

    module_id = filters.NumberFilter(
        field_name='module__id',
        help_text='Filtrer par ID du module'
    )

    course = filters.ModelChoiceFilter(
        queryset=Course.objects.all(),
        field_name='module__course',
        help_text='Filtrer par cours'
    )

    course_id = filters.NumberFilter(
        field_name='module__course__id',
        help_text='Filtrer par ID du cours'
    )

    title = filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        help_text='Filtrer par titre (recherche partielle)'
    )

    class Meta:
        model = Quiz
        fields = ['module', 'module_id', 'course', 'course_id', 'title']


class QuizQuestionFilter(filters.FilterSet):
    """Filtre pour les questions de quiz"""
    quiz = filters.ModelChoiceFilter(
        queryset=Quiz.objects.all(),
        field_name='quiz',
        help_text='Filtrer par quiz'
    )

    quiz_id = filters.NumberFilter(
        field_name='quiz__id',
        help_text='Filtrer par ID du quiz'
    )

    title = filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        help_text='Filtrer par titre (recherche partielle)'
    )

    class Meta:
        model = QuizQuestion
        fields = ['quiz', 'quiz_id', 'title']


class QuizChoiceFilter(filters.FilterSet):
    """Filtre pour les choix de réponse"""
    question = filters.ModelChoiceFilter(
        queryset=QuizQuestion.objects.all(),
        field_name='question',
        help_text='Filtrer par question'
    )

    question_id = filters.NumberFilter(
        field_name='question__id',
        help_text='Filtrer par ID de la question'
    )

    is_correct = filters.BooleanFilter(
        field_name='is_correct',
        help_text='Filtrer par réponses correctes/incorrectes'
    )

    class Meta:
        model = QuizChoice
        fields = ['question', 'question_id', 'is_correct']


class QuizResultFilter(filters.FilterSet):
    """Filtre pour les résultats de quiz"""
    user = filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        field_name='user',
        help_text='Filtrer par utilisateur'
    )

    user_id = filters.NumberFilter(
        field_name='user__id',
        help_text='Filtrer par ID utilisateur'
    )

    quiz = filters.ModelChoiceFilter(
        queryset=Quiz.objects.all(),
        field_name='quiz',
        help_text='Filtrer par quiz'
    )

    quiz_id = filters.NumberFilter(
        field_name='quiz__id',
        help_text='Filtrer par ID du quiz'
    )

    score_min = filters.NumberFilter(
        field_name='score',
        lookup_expr='gte',
        help_text='Score minimum'
    )

    score_max = filters.NumberFilter(
        field_name='score',
        lookup_expr='lte',
        help_text='Score maximum'
    )

    submitted_after = filters.DateTimeFilter(
        field_name='submitted_at',
        lookup_expr='gte',
        help_text='Soumis après cette date'
    )

    submitted_before = filters.DateTimeFilter(
        field_name='submitted_at',
        lookup_expr='lte',
        help_text='Soumis avant cette date'
    )

    class Meta:
        model = QuizResult
        fields = ['user', 'user_id', 'quiz', 'quiz_id', 'score_min', 'score_max', 'submitted_after', 'submitted_before']


class ProgressFilter(filters.FilterSet):
    """Filtre pour les progrès"""
    user = filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        field_name='user',
        help_text='Filtrer par utilisateur'
    )

    user_id = filters.NumberFilter(
        field_name='user__id',
        help_text='Filtrer par ID utilisateur'
    )

    content = filters.ModelChoiceFilter(
        queryset=Content.objects.all(),
        field_name='content',
        help_text='Filtrer par contenu'
    )

    content_id = filters.NumberFilter(
        field_name='content__id',
        help_text='Filtrer par ID du contenu'
    )

    course = filters.ModelChoiceFilter(
        queryset=Course.objects.all(),
        field_name='content__module__course',
        help_text='Filtrer par cours'
    )

    course_id = filters.NumberFilter(
        field_name='content__module__course__id',
        help_text='Filtrer par ID du cours'
    )

    module = filters.ModelChoiceFilter(
        queryset=Module.objects.all(),
        field_name='content__module',
        help_text='Filtrer par module'
    )

    module_id = filters.NumberFilter(
        field_name='content__module__id',
        help_text='Filtrer par ID du module'
    )

    is_completed = filters.BooleanFilter(
        field_name='is_completed',
        help_text='Filtrer par statut de complétion'
    )

    completed_after = filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='gte',
        help_text='Complété après cette date'
    )

    completed_before = filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='lte',
        help_text='Complété avant cette date'
    )

    class Meta:
        model = Progress
        fields = [
            'user', 'user_id', 'content', 'content_id', 'course', 'course_id',
            'module', 'module_id', 'is_completed', 'completed_after', 'completed_before'
        ]


class CertificateFilter(filters.FilterSet):
    """Filtre pour les certificats"""
    user = filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        field_name='user',
        help_text='Filtrer par utilisateur'
    )

    user_id = filters.NumberFilter(
        field_name='user__id',
        help_text='Filtrer par ID utilisateur'
    )

    course = filters.ModelChoiceFilter(
        queryset=Course.objects.all(),
        field_name='course',
        help_text='Filtrer par cours'
    )

    course_id = filters.NumberFilter(
        field_name='course__id',
        help_text='Filtrer par ID du cours'
    )

    issued_after = filters.DateTimeFilter(
        field_name='issued_at',
        lookup_expr='gte',
        help_text='Émis après cette date'
    )

    issued_before = filters.DateTimeFilter(
        field_name='issued_at',
        lookup_expr='lte',
        help_text='Émis avant cette date'
    )

    class Meta:
        model = Certificate
        fields = ['user', 'user_id', 'course', 'course_id', 'issued_after', 'issued_before']
