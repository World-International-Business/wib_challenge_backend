from django_filters import rest_framework as filters

from questions.models import Question


class QuestionFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Question.
    """
    evaluation = filters.NumberFilter(field_name='evaluation_id', lookup_expr='exact')
    technology = filters.CharFilter(field_name='technology__name', lookup_expr='iexact')
    profession = filters.CharFilter(field_name='technology__professions__title', lookup_expr='iexact')
    date_min = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    date_max = filters.DateFilter(field_name='created_at', lookup_expr='lte')
    order_by = filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
            ('difficulty', 'difficulty'),
        ),
        field_labels={
            'created_at': 'Date de création',
            'difficulty': 'Difficulté',
        }
    )

    class Meta:
        model = Question
        fields = {
            'difficulty': ['exact'],
            'status': ['exact'],
            'publisher': ['exact'],
        }
