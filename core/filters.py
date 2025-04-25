from django_filters import rest_framework as filters

from core.models import Technology, Profession


class TechnologyFilter(filters.FilterSet):
    profession = filters.NumberFilter(field_name='professions__id', lookup_expr='exact')

    class Meta:
        model = Technology
        fields = ['profession']
        order_by = ['name']


class ProfessionFilter(filters.FilterSet):
    technology = filters.NumberFilter(field_name='technologies__id', lookup_expr='exact')

    class Meta:
        model = Profession
        fields = ['technologies']
        order_by = ['title']
