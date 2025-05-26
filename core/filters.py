from django_filters import rest_framework as filters

from core.models import Technology, Profession, Domain


class DomainFilter(filters.FilterSet):
    class Meta:
        model = Domain
        fields = ['name']
        order_by = ['name']


class TechnologyFilter(filters.FilterSet):
    profession = filters.NumberFilter(field_name='professions__id', lookup_expr='exact')
    domain = filters.NumberFilter(field_name='professions__domain__id', lookup_expr='exact')

    class Meta:
        model = Technology
        fields = ['profession', 'domain']
        order_by = ['name']


class ProfessionFilter(filters.FilterSet):
    technology = filters.NumberFilter(field_name='technologies__id', lookup_expr='exact')
    domain = filters.NumberFilter(field_name='domain__id', lookup_expr='exact')

    class Meta:
        model = Profession
        fields = ['technologies', 'domain']
        order_by = ['title']
