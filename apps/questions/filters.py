from django.db.models import Q
from django_filters import rest_framework as filters

from apps.questions.models import Question


class QuestionFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Question avec filtres avancés.
    """
    technology = filters.CharFilter(field_name='technology__name', lookup_expr='icontains')
    technology_exact = filters.CharFilter(field_name='technology__name', lookup_expr='iexact')

    profession = filters.CharFilter(field_name='technology__professions__title', lookup_expr='icontains')

    date_min = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    date_max = filters.DateFilter(field_name='created_at', lookup_expr='lte')
    updated_after = filters.DateTimeFilter(field_name='updated_at', lookup_expr='gte')

    publisher_email = filters.CharFilter(field_name='publisher__email', lookup_expr='icontains')
    publisher_name = filters.CharFilter(method='filter_by_publisher_name')

    search = filters.CharFilter(method='filter_search')
    title_contains = filters.CharFilter(field_name='title', lookup_expr='icontains')

    duration_min = filters.NumberFilter(field_name='duration', lookup_expr='gte')
    duration_max = filters.NumberFilter(field_name='duration', lookup_expr='lte')

    weight_min = filters.NumberFilter(method='filter_by_weight_min')
    weight_max = filters.NumberFilter(method='filter_by_weight_max')

    has_explanation = filters.BooleanFilter(method='filter_has_explanation')
    has_description = filters.BooleanFilter(method='filter_has_description')

    order_by = filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('difficulty', 'difficulty'),
            ('duration', 'duration'),
            ('title', 'title'),
            ('publisher__email', 'publisher_email'),
        ),
        field_labels={
            'created_at': 'Date de création',
            'updated_at': 'Dernière modification',
            'difficulty': 'Difficulté',
            'duration': 'Durée',
            'title': 'Titre',
            'publisher_email': 'Email éditeur',
        }
    )

    class Meta:
        model = Question
        fields = {
            'difficulty': ['exact', 'in'],
            'status': ['exact', 'in'],
            'publisher': ['exact'],
            'technology': ['exact'],
            'duration': ['exact', 'gte', 'lte'],
        }

    def filter_by_publisher_name(self, queryset, name, value):
        """Filtre par nom ou prénom de l'éditeur"""
        if not value:
            return queryset
        return queryset.filter(
            Q(publisher__first_name__icontains=value) |
            Q(publisher__last_name__icontains=value)
        )

    def filter_search(self, queryset, name, value):
        """Recherche globale dans titre, description et explication"""
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) |
            Q(description__icontains=value) |
            Q(explanation__icontains=value)
        )

    def filter_by_weight_min(self, queryset, name, value):
        """Filtre par poids minimum basé sur la difficulté"""
        if not value:
            return queryset

        difficulties = []
        for difficulty, weight in Question.DIFFICULTY_WEIGHTS.items():
            if weight >= value:
                difficulties.append(difficulty)

        return queryset.filter(difficulty__in=difficulties)

    def filter_by_weight_max(self, queryset, name, value):
        """Filtre par poids maximum basé sur la difficulté"""
        if not value:
            return queryset

        difficulties = []
        for difficulty, weight in Question.DIFFICULTY_WEIGHTS.items():
            if weight <= value:
                difficulties.append(difficulty)

        return queryset.filter(difficulty__in=difficulties)

    def filter_has_explanation(self, queryset, name, value):
        """Filtre les questions qui ont ou n'ont pas d'explication"""
        if value is None:
            return queryset
        if value:
            return queryset.exclude(Q(explanation__isnull=True) | Q(explanation__exact=''))
        else:
            return queryset.filter(Q(explanation__isnull=True) | Q(explanation__exact=''))

    def filter_has_description(self, queryset, name, value):
        """Filtre les questions qui ont ou n'ont pas de description"""
        if value is None:
            return queryset
        if value:
            return queryset.exclude(Q(description__isnull=True) | Q(description__exact=''))
        else:
            return queryset.filter(Q(description__isnull=True) | Q(description__exact=''))
