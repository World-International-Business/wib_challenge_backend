import django_filters

from .models import (
    Course, Module, Content, Quiz, QuizQuestion, QuizChoice, QuizResult,
    Progress, Certificate, SkillLevel, ContentType
)


class CourseFilter(django_filters.FilterSet):
    """Filtres pour les cours"""
    title = django_filters.CharFilter(lookup_expr='icontains', label='Titre')
    description = django_filters.CharFilter(lookup_expr='icontains', label='Description')
    level = django_filters.ChoiceFilter(choices=SkillLevel.choices, label='Niveau')
    is_free = django_filters.BooleanFilter(label='Gratuit')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Créé après')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Créé avant')

    class Meta:
        model = Course
        fields = ['title', 'description', 'level', 'is_free', 'created_after', 'created_before']


class ModuleFilter(django_filters.FilterSet):
    """Filtres pour les modules"""
    title = django_filters.CharFilter(lookup_expr='icontains', label='Titre')
    description = django_filters.CharFilter(lookup_expr='icontains', label='Description')
    course = django_filters.ModelChoiceFilter(
        queryset=Course.objects.all(),
        label='Cours'
    )
    course_level = django_filters.ChoiceFilter(
        field_name='course__level',
        choices=SkillLevel.choices,
        label='Niveau du cours'
    )
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Créé après')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Créé avant')

    class Meta:
        model = Module
        fields = ['title', 'description', 'course', 'course_level', 'created_after', 'created_before']


class ContentFilter(django_filters.FilterSet):
    """Filtres pour les contenus"""
    title = django_filters.CharFilter(lookup_expr='icontains', label='Titre')
    content_type = django_filters.ChoiceFilter(choices=ContentType.choices, label='Type de contenu')
    module = django_filters.ModelChoiceFilter(
        queryset=Module.objects.all(),
        label='Module'
    )
    course = django_filters.ModelChoiceFilter(
        field_name='module__course',
        queryset=Course.objects.all(),
        label='Cours'
    )
    course_level = django_filters.ChoiceFilter(
        field_name='module__course__level',
        choices=SkillLevel.choices,
        label='Niveau du cours'
    )
    has_file = django_filters.BooleanFilter(
        field_name='resource_file',
        lookup_expr='isnull',
        exclude=True,
        label='A un fichier'
    )
    has_url = django_filters.BooleanFilter(
        field_name='resource_url',
        lookup_expr='isnull',
        exclude=True,
        label='A une URL'
    )
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Créé après')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Créé avant')

    class Meta:
        model = Content
        fields = [
            'title', 'content_type', 'module', 'course', 'course_level',
            'has_file', 'has_url', 'created_after', 'created_before'
        ]


class QuizFilter(django_filters.FilterSet):
    """Filtres pour les quiz"""
    title = django_filters.CharFilter(lookup_expr='icontains', label='Titre')
    description = django_filters.CharFilter(lookup_expr='icontains', label='Description')
    module = django_filters.ModelChoiceFilter(
        queryset=Module.objects.all(),
        label='Module'
    )
    course = django_filters.ModelChoiceFilter(
        field_name='module__course',
        queryset=Course.objects.all(),
        label='Cours'
    )
    course_level = django_filters.ChoiceFilter(
        field_name='module__course__level',
        choices=SkillLevel.choices,
        label='Niveau du cours'
    )
    min_questions = django_filters.NumberFilter(
        field_name='questions',
        lookup_expr='count__gte',
        distinct=True,
        label='Minimum de questions'
    )
    max_questions = django_filters.NumberFilter(
        field_name='questions',
        lookup_expr='count__lte',
        distinct=True,
        label='Maximum de questions'
    )
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Créé après')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Créé avant')

    class Meta:
        model = Quiz
        fields = [
            'title', 'description', 'module', 'course', 'course_level',
            'min_questions', 'max_questions', 'created_after', 'created_before'
        ]


class QuizQuestionFilter(django_filters.FilterSet):
    """Filtres pour les questions de quiz"""
    title = django_filters.CharFilter(lookup_expr='icontains', label='Question')
    description = django_filters.CharFilter(lookup_expr='icontains', label='Description')
    quiz = django_filters.ModelChoiceFilter(
        queryset=Quiz.objects.all(),
        label='Quiz'
    )
    module = django_filters.ModelChoiceFilter(
        field_name='quiz__module',
        queryset=Module.objects.all(),
        label='Module'
    )
    course = django_filters.ModelChoiceFilter(
        field_name='quiz__module__course',
        queryset=Course.objects.all(),
        label='Cours'
    )
    min_choices = django_filters.NumberFilter(
        field_name='choices',
        lookup_expr='count__gte',
        distinct=True,
        label='Minimum de choix'
    )
    max_choices = django_filters.NumberFilter(
        field_name='choices',
        lookup_expr='count__lte',
        distinct=True,
        label='Maximum de choix'
    )
    has_explanation = django_filters.BooleanFilter(
        field_name='explanation',
        lookup_expr='isnull',
        exclude=True,
        label='A une explication'
    )
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Créé après')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Créé avant')

    class Meta:
        model = QuizQuestion
        fields = [
            'title', 'description', 'quiz', 'module', 'course',
            'min_choices', 'max_choices', 'has_explanation', 'created_after', 'created_before'
        ]


class QuizChoiceFilter(django_filters.FilterSet):
    """Filtres pour les choix de réponse"""
    text = django_filters.CharFilter(lookup_expr='icontains', label='Texte')
    is_correct = django_filters.BooleanFilter(label='Réponse correcte')
    question = django_filters.ModelChoiceFilter(
        queryset=QuizQuestion.objects.all(),
        label='Question'
    )
    quiz = django_filters.ModelChoiceFilter(
        field_name='question__quiz',
        queryset=Quiz.objects.all(),
        label='Quiz'
    )
    module = django_filters.ModelChoiceFilter(
        field_name='question__quiz__module',
        queryset=Module.objects.all(),
        label='Module'
    )
    course = django_filters.ModelChoiceFilter(
        field_name='question__quiz__module__course',
        queryset=Course.objects.all(),
        label='Cours'
    )

    class Meta:
        model = QuizChoice
        fields = ['text', 'is_correct', 'question', 'quiz', 'module', 'course']


class QuizResultFilter(django_filters.FilterSet):
    """Filtres pour les résultats de quiz"""
    quiz = django_filters.ModelChoiceFilter(
        queryset=Quiz.objects.all(),
        label='Quiz'
    )
    module = django_filters.ModelChoiceFilter(
        field_name='quiz__module',
        queryset=Module.objects.all(),
        label='Module'
    )
    course = django_filters.ModelChoiceFilter(
        field_name='quiz__module__course',
        queryset=Course.objects.all(),
        label='Cours'
    )
    min_score = django_filters.NumberFilter(field_name='score', lookup_expr='gte', label='Score minimum')
    max_score = django_filters.NumberFilter(field_name='score', lookup_expr='lte', label='Score maximum')
    passed = django_filters.BooleanFilter(
        field_name='score',
        lookup_expr='gte',
        method='filter_passed',
        label='Quiz réussi (≥70%)'
    )
    submitted_after = django_filters.DateTimeFilter(
        field_name='submitted_at',
        lookup_expr='gte',
        label='Soumis après'
    )
    submitted_before = django_filters.DateTimeFilter(
        field_name='submitted_at',
        lookup_expr='lte',
        label='Soumis avant'
    )

    def filter_passed(self, queryset, name, value):
        """Filtre pour les quiz réussis (score >= 70)"""
        if value:
            return queryset.filter(score__gte=70)
        else:
            return queryset.filter(score__lt=70)

    class Meta:
        model = QuizResult
        fields = [
            'quiz', 'module', 'course', 'min_score', 'max_score', 'passed',
            'submitted_after', 'submitted_before'
        ]


class ProgressFilter(django_filters.FilterSet):
    """Filtres pour les progrès"""
    content = django_filters.ModelChoiceFilter(
        queryset=Content.objects.all(),
        label='Contenu'
    )
    module = django_filters.ModelChoiceFilter(
        field_name='content__module',
        queryset=Module.objects.all(),
        label='Module'
    )
    course = django_filters.ModelChoiceFilter(
        field_name='content__module__course',
        queryset=Course.objects.all(),
        label='Cours'
    )
    content_type = django_filters.ChoiceFilter(
        field_name='content__content_type',
        choices=ContentType.choices,
        label='Type de contenu'
    )
    course_level = django_filters.ChoiceFilter(
        field_name='content__module__course__level',
        choices=SkillLevel.choices,
        label='Niveau du cours'
    )
    is_completed = django_filters.BooleanFilter(label='Terminé')
    completed_after = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='gte',
        label='Terminé après'
    )
    completed_before = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='lte',
        label='Terminé avant'
    )

    class Meta:
        model = Progress
        fields = [
            'content', 'module', 'course', 'content_type', 'course_level',
            'is_completed', 'completed_after', 'completed_before'
        ]


class CertificateFilter(django_filters.FilterSet):
    """Filtres pour les certificats"""
    course = django_filters.ModelChoiceFilter(
        queryset=Course.objects.all(),
        label='Cours'
    )
    course_level = django_filters.ChoiceFilter(
        field_name='course__level',
        choices=SkillLevel.choices,
        label='Niveau du cours'
    )
    course_title = django_filters.CharFilter(
        field_name='course__title',
        lookup_expr='icontains',
        label='Titre du cours'
    )
    issued_after = django_filters.DateTimeFilter(
        field_name='issued_at',
        lookup_expr='gte',
        label='Émis après'
    )
    issued_before = django_filters.DateTimeFilter(
        field_name='issued_at',
        lookup_expr='lte',
        label='Émis avant'
    )
    has_file = django_filters.BooleanFilter(
        field_name='file',
        lookup_expr='isnull',
        exclude=True,
        label='A un fichier'
    )

    class Meta:
        model = Certificate
        fields = [
            'course', 'course_level', 'course_title',
            'issued_after', 'issued_before', 'has_file'
        ]
