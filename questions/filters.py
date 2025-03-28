from django_filters import rest_framework as filters

from questions.models import Question


class QuestionFilterSet(filters.FilterSet):
    """
    FilterSet for the Question model.
    """
    # TODO filter by tests
    technology = filters.CharFilter(field_name='technology__name', lookup_expr='exact')
    profession = filters.CharFilter(field_name='technology__professions', lookup_expr='exact')
    order_by = filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
        ),
        field_labels={
            'created_at': 'Date de création',
        }
    )

    class Meta:
        model = Question
        fields = {
            'difficulty': ['exact'],
            'status': ['exact'],
        }
