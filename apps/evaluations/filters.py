from django.db.models import Q
from django_filters import rest_framework as filters

from apps.evaluations.models import Evaluation, SubmissionAttempt, Answer, Submission, Candidate, Participant


class EvaluationFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Evaluation avec filtres avancés.
    """
    technology = filters.CharFilter(field_name='technology__name', lookup_expr='icontains')
    technology_exact = filters.CharFilter(field_name='technology__name', lookup_expr='iexact')

    profession = filters.CharFilter(field_name='profession__title', lookup_expr='icontains')
    profession_exact = filters.CharFilter(field_name='profession__title', lookup_expr='iexact')

    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    updated_after = filters.DateTimeFilter(field_name='updated_at', lookup_expr='gte')

    publisher_email = filters.CharFilter(field_name='publisher__email', lookup_expr='icontains')
    publisher_name = filters.CharFilter(method='filter_by_publisher_name')

    search = filters.CharFilter(method='filter_search')
    title_contains = filters.CharFilter(field_name='title', lookup_expr='icontains')

    is_constructed = filters.BooleanFilter(method='filter_is_constructed')
    has_questions = filters.BooleanFilter(method='filter_has_questions')
    has_competition = filters.BooleanFilter(method='filter_has_competition')

    questions_count_min = filters.NumberFilter(method='filter_questions_count_min')
    questions_count_max = filters.NumberFilter(method='filter_questions_count_max')

    order_by = filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('title', 'title'),
            ('difficulty', 'difficulty'),
            ('evaluation_type', 'evaluation_type'),
        ),
        field_labels={
            'created_at': 'Date de création',
            'updated_at': 'Dernière modification',
            'title': 'Titre',
            'difficulty': 'Difficulté',
            'evaluation_type': 'Type d\'évaluation',
        }
    )

    class Meta:
        model = Evaluation
        fields = {
            'difficulty': ['exact', 'in'],
            'evaluation_type': ['exact', 'in'],
            'publisher': ['exact'],
            'technology': ['exact'],
            'profession': ['exact'],
            'archived': ['exact'],
        }

    def filter_by_publisher_name(self, queryset, name, value):
        """Filtre par nom ou prénom du publisher"""
        if not value:
            return queryset
        return queryset.filter(
            Q(publisher__first_name__icontains=value) |
            Q(publisher__last_name__icontains=value)
        )

    def filter_search(self, queryset, name, value):
        """Recherche globale dans titre et description"""
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) |
            Q(description__icontains=value)
        )

    def filter_is_constructed(self, queryset, name, value):
        """Filtre les évaluations construites/non construites"""
        if value is None:
            return queryset

        constructed_ids = []
        for evaluation in queryset:
            if evaluation.is_constructed == value:
                constructed_ids.append(evaluation.id)

        return queryset.filter(id__in=constructed_ids)

    def filter_has_questions(self, queryset, name, value):
        """Filtre les évaluations avec ou sans questions"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(questions__isnull=False).distinct()
        else:
            return queryset.filter(questions__isnull=True)

    def filter_has_competition(self, queryset, name, value):
        """Filtre les évaluations avec ou sans compétition"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(competition__isnull=False)
        else:
            return queryset.filter(competition__isnull=True)

    def filter_questions_count_min(self, queryset, name, value):
        """Filtre par nombre minimum de questions"""
        if not value:
            return queryset

        valid_ids = []
        for evaluation in queryset:
            if evaluation.questions.count() >= value:
                valid_ids.append(evaluation.id)

        return queryset.filter(id__in=valid_ids)

    def filter_questions_count_max(self, queryset, name, value):
        """Filtre par nombre maximum de questions"""
        if not value:
            return queryset

        valid_ids = []
        for evaluation in queryset:
            if evaluation.questions.count() <= value:
                valid_ids.append(evaluation.id)

        return queryset.filter(id__in=valid_ids)


class SubmissionAttemptFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle SubmissionAttempt.
    """
    evaluation_title = filters.CharFilter(field_name='evaluation__title', lookup_expr='icontains')
    evaluation_type = filters.CharFilter(field_name='evaluation__evaluation_type', lookup_expr='exact')

    started_after = filters.DateTimeFilter(field_name='started_at', lookup_expr='gte')
    started_before = filters.DateTimeFilter(field_name='started_at', lookup_expr='lte')
    ended_after = filters.DateTimeFilter(field_name='ended_at', lookup_expr='gte')
    ended_before = filters.DateTimeFilter(field_name='ended_at', lookup_expr='lte')

    participant_type = filters.CharFilter(field_name='participant__type', lookup_expr='exact')
    participant_email = filters.CharFilter(method='filter_by_participant_email')
    participant_name = filters.CharFilter(method='filter_by_participant_name')

    is_finished = filters.BooleanFilter(method='filter_is_finished')
    has_submission = filters.BooleanFilter(method='filter_has_submission')

    order_by = filters.OrderingFilter(
        fields=(
            ('started_at', 'started_at'),
            ('ended_at', 'ended_at'),
            ('is_completed', 'is_completed'),
            ('corrected', 'corrected'),
        ),
        field_labels={
            'started_at': 'Date de début',
            'ended_at': 'Date de fin',
            'is_completed': 'Complété',
            'corrected': 'Corrigé',
        }
    )

    class Meta:
        model = SubmissionAttempt
        fields = {
            'evaluation': ['exact'],
            'participant': ['exact'],
            'is_completed': ['exact'],
            'corrected': ['exact'],
        }

    def filter_by_participant_email(self, queryset, name, value):
        """Filtre par email du participant"""
        if not value:
            return queryset

        return queryset.filter(
            Q(participant__user__email__icontains=value) |
            Q(participant__candidate__email__icontains=value)
        )

    def filter_by_participant_name(self, queryset, name, value):
        """Filtre par nom du participant"""
        if not value:
            return queryset

        return queryset.filter(
            Q(participant__user__first_name__icontains=value) |
            Q(participant__user__last_name__icontains=value) |
            Q(participant__candidate__full_name__icontains=value)
        )

    def filter_is_finished(self, queryset, name, value):
        """Filtre les tentatives finies/non finies"""
        if value is None:
            return queryset

        finished_ids = []
        for attempt in queryset:
            if attempt.is_finished == value:
                finished_ids.append(attempt.id)

        return queryset.filter(id__in=finished_ids)

    def filter_has_submission(self, queryset, name, value):
        """Filtre les tentatives avec ou sans soumission"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(submission__isnull=False)
        else:
            return queryset.filter(submission__isnull=True)


class AnswerFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Answer.
    """
    question_text = filters.CharFilter(field_name='question__title', lookup_expr='icontains')
    question_difficulty = filters.CharFilter(field_name='question__difficulty', lookup_expr='exact')

    attempt_evaluation = filters.CharFilter(field_name='attempt__evaluation__title', lookup_expr='icontains')

    answered_after = filters.DateTimeFilter(field_name='answered_at', lookup_expr='gte')
    answered_before = filters.DateTimeFilter(field_name='answered_at', lookup_expr='lte')

    delta_time_min = filters.NumberFilter(field_name='delta_time', lookup_expr='gte')
    delta_time_max = filters.NumberFilter(field_name='delta_time', lookup_expr='lte')

    score_min = filters.NumberFilter(field_name='score', lookup_expr='gte')
    score_max = filters.NumberFilter(field_name='score', lookup_expr='lte')

    class Meta:
        model = Answer
        fields = {
            'attempt': ['exact'],
            'question': ['exact'],
            'is_correct': ['exact'],
            'status': ['exact', 'in'],
            'score': ['exact', 'gte', 'lte'],
            'delta_time': ['exact', 'gte', 'lte'],
        }


class SubmissionFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Submission.
    """
    evaluation_title = filters.CharFilter(field_name='attempt__evaluation__title', lookup_expr='icontains')
    evaluation_type = filters.CharFilter(field_name='attempt__evaluation__evaluation_type', lookup_expr='exact')

    submitted_after = filters.DateTimeFilter(field_name='submitted_at', lookup_expr='gte')
    submitted_before = filters.DateTimeFilter(field_name='submitted_at', lookup_expr='lte')

    score_min = filters.NumberFilter(field_name='score', lookup_expr='gte')
    score_max = filters.NumberFilter(field_name='score', lookup_expr='lte')
    score_range = filters.RangeFilter(field_name='score')

    has_personality_detail = filters.BooleanFilter(method='filter_has_personality_detail')

    class Meta:
        model = Submission
        fields = {
            'score': ['exact', 'gte', 'lte'],
        }

    def filter_has_personality_detail(self, queryset, name, value):
        """Filtre les soumissions avec ou sans détails de personnalité"""
        if value is None:
            return queryset
        if value:
            return queryset.exclude(Q(personality_detail__isnull=True) | Q(personality_detail__exact=''))
        else:
            return queryset.filter(Q(personality_detail__isnull=True) | Q(personality_detail__exact=''))


class ParticipantFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Participant.
    """
    type = filters.ChoiceFilter(field_name='type', choices=Participant.Type.choices)

    # Filtres pour les utilisateurs
    user_email = filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    user_name = filters.CharFilter(method='filter_by_user_name')

    # Filtres pour les candidats
    candidate_email = filters.CharFilter(field_name='candidate__email', lookup_expr='icontains')
    candidate_name = filters.CharFilter(field_name='candidate__full_name', lookup_expr='icontains')
    candidate_owner = filters.CharFilter(field_name='candidate__owner__email', lookup_expr='icontains')

    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    search = filters.CharFilter(method='filter_search')
    email_contains = filters.CharFilter(method='filter_by_email')
    name_contains = filters.CharFilter(method='filter_by_name')
    evaluation = filters.NumberFilter(method='filter_by_evaluation')

    class Meta:
        model = Participant
        fields = {
            'type': ['exact'],
            'user': ['exact'],
            'candidate': ['exact'],
        }

    def filter_by_user_name(self, queryset, name, value):
        """Filtre par nom de l'utilisateur"""
        if not value:
            return queryset
        return queryset.filter(
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value)
        )

    def filter_by_email(self, queryset, name, value):
        """Filtre par email du participant"""
        if not value:
            return queryset
        return queryset.filter(
            Q(user__email__icontains=value) |
            Q(candidate__email__icontains=value)
        )

    def filter_by_name(self, queryset, name, value):
        """Filtre par nom du participant"""
        if not value:
            return queryset
        return queryset.filter(
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value) |
            Q(candidate__full_name__icontains=value)
        )

    def filter_search(self, queryset, name, value):
        """Recherche globale dans nom et email"""
        if not value:
            return queryset
        return queryset.filter(
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value) |
            Q(user__email__icontains=value) |
            Q(candidate__full_name__icontains=value) |
            Q(candidate__email__icontains=value)
        )

    def filter_by_evaluation(self, queryset, name, value):
        """Filtre les participants qui ont des tentatives pour une évaluation spécifique"""
        if not value:
            return queryset

        participant_ids = SubmissionAttempt.objects.filter(
            evaluation_id=value
        ).values_list('participant_id', flat=True)

        return queryset.filter(id__in=participant_ids)


# Garder CandidateFilterSet pour la rétrocompatibilité si nécessaire
CandidateFilterSet = filters.FilterSet


class CandidateFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Candidate (rétrocompatibilité).
    """
    owner_email = filters.CharFilter(field_name='owner__email', lookup_expr='icontains')
    owner_name = filters.CharFilter(method='filter_by_owner_name')

    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    search = filters.CharFilter(method='filter_search')
    name_contains = filters.CharFilter(field_name='full_name', lookup_expr='icontains')
    email_contains = filters.CharFilter(field_name='email', lookup_expr='icontains')
    evaluation = filters.NumberFilter(method='filter_by_evaluation')

    class Meta:
        model = Candidate
        fields = {
            'owner': ['exact'],
            'email': ['exact', 'icontains'],
            'full_name': ['icontains'],
        }

    def filter_by_owner_name(self, queryset, name, value):
        """Filtre par nom du propriétaire"""
        if not value:
            return queryset
        return queryset.filter(
            Q(owner__first_name__icontains=value) |
            Q(owner__last_name__icontains=value)
        )

    def filter_search(self, queryset, name, value):
        """Recherche globale dans nom et email"""
        if not value:
            return queryset
        return queryset.filter(
            Q(full_name__icontains=value) |
            Q(email__icontains=value)
        )

    def filter_by_evaluation(self, queryset, name, value):
        """Filtre les candidats qui ont des tentatives pour une évaluation spécifique"""
        if not value:
            return queryset

        candidate_ids = SubmissionAttempt.objects.filter(
            evaluation_id=value,
            participant__candidate__isnull=False
        ).values_list('participant__candidate_id', flat=True)

        return queryset.filter(id__in=candidate_ids)
