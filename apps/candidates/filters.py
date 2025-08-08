from django.db.models import Q
from django_filters import rest_framework as filters

from apps.candidates.models import (
    CandidateProfile, Experience, Education, Language,
    Project
)


class CandidateProfileFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle CandidateProfile avec filtres avancés.
    """
    profession_name = filters.CharFilter(field_name='profession__title', lookup_expr='icontains')
    profession_category = filters.CharFilter(field_name='profession__category', lookup_expr='icontains')

    location_contains = filters.CharFilter(field_name='location', lookup_expr='icontains')
    location_exact = filters.CharFilter(field_name='location', lookup_expr='iexact')

    experience_min = filters.NumberFilter(field_name='years_experience', lookup_expr='gte')
    experience_max = filters.NumberFilter(field_name='years_experience', lookup_expr='lte')
    other_experience_min = filters.NumberFilter(field_name='other_years_experience', lookup_expr='gte')
    other_experience_max = filters.NumberFilter(field_name='other_years_experience', lookup_expr='lte')

    degree_min = filters.NumberFilter(field_name='highest_degree', lookup_expr='gte')
    degree_max = filters.NumberFilter(field_name='highest_degree', lookup_expr='lte')

    technology = filters.CharFilter(field_name='technologies__name', lookup_expr='icontains')
    technology_level_min = filters.NumberFilter(field_name='profile_technologies__level', lookup_expr='gte')
    technology_level_max = filters.NumberFilter(field_name='profile_technologies__level', lookup_expr='lte')

    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    user_email = filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    user_name = filters.CharFilter(method='filter_by_user_name')
    user_active = filters.BooleanFilter(field_name='user__is_active')

    search = filters.CharFilter(method='filter_search')

    has_biography = filters.BooleanFilter(method='filter_has_biography')
    has_projects = filters.BooleanFilter(method='filter_has_projects')
    has_experiences = filters.BooleanFilter(method='filter_has_experiences')

    order_by = filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('years_experience', 'years_experience'),
            ('highest_degree', 'highest_degree'),
            ('user__first_name', 'user_name'),
            ('profession__title', 'profession'),
        ),
        field_labels={
            'created_at': 'Date de création',
            'updated_at': 'Dernière modification',
            'years_experience': 'Expérience',
            'highest_degree': 'Diplôme',
            'user_name': 'Nom utilisateur',
            'profession': 'Profession',
        }
    )

    class Meta:
        model = CandidateProfile
        fields = {
            'disability': ['exact'],
            'open_to_work': ['exact'],
            'profession': ['exact'],
            'years_experience': ['exact', 'gte', 'lte'],
            'highest_degree': ['exact', 'gte', 'lte'],
        }

    def filter_by_user_name(self, queryset, name, value):
        """Filtre par nom ou prénom de l'utilisateur"""
        if not value:
            return queryset
        return queryset.filter(
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value)
        )

    def filter_search(self, queryset, name, value):
        """Recherche globale dans plusieurs champs"""
        if not value:
            return queryset
        return queryset.filter(
            Q(short_bio__icontains=value) |
            Q(biography__icontains=value) |
            Q(interested_by__icontains=value) |
            Q(location__icontains=value) |
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value) |
            Q(user__email__icontains=value)
        )

    def filter_has_biography(self, queryset, name, value):
        """Filtre les profils avec ou sans biographie"""
        if value is None:
            return queryset
        if value:
            return queryset.exclude(Q(biography__isnull=True) | Q(biography__exact=''))
        else:
            return queryset.filter(Q(biography__isnull=True) | Q(biography__exact=''))

    def filter_has_projects(self, queryset, name, value):
        """Filtre les profils avec ou sans projets"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(projects__isnull=False).distinct()
        else:
            return queryset.filter(projects__isnull=True)

    def filter_has_experiences(self, queryset, name, value):
        """Filtre les profils avec ou sans expériences"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(experiences__isnull=False).distinct()
        else:
            return queryset.filter(experiences__isnull=True)


class ExperienceFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Experience.
    """
    company_name = filters.CharFilter(field_name='company', lookup_expr='icontains')
    title_contains = filters.CharFilter(field_name='title', lookup_expr='icontains')
    location_contains = filters.CharFilter(field_name='location', lookup_expr='icontains')

    start_date_after = filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_before = filters.DateFilter(field_name='start_date', lookup_expr='lte')
    end_date_after = filters.DateFilter(field_name='end_date', lookup_expr='gte')
    end_date_before = filters.DateFilter(field_name='end_date', lookup_expr='lte')

    profile_user_email = filters.CharFilter(field_name='profile__user__email', lookup_expr='icontains')

    search = filters.CharFilter(method='filter_search')

    class Meta:
        model = Experience
        fields = {
            'still_working': ['exact'],
            'profile': ['exact'],
            'start_date': ['exact', 'gte', 'lte'],
            'end_date': ['exact', 'gte', 'lte', 'isnull'],
        }

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) |
            Q(company__icontains=value) |
            Q(description__icontains=value) |
            Q(location__icontains=value)
        )


class ProjectFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Project.
    """
    name_contains = filters.CharFilter(field_name='name', lookup_expr='icontains')
    description_contains = filters.CharFilter(field_name='description', lookup_expr='icontains')

    start_date_after = filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_before = filters.DateFilter(field_name='start_date', lookup_expr='lte')

    profile_user_email = filters.CharFilter(field_name='profile__user__email', lookup_expr='icontains')
    has_link = filters.BooleanFilter(method='filter_has_link')
    has_images = filters.BooleanFilter(method='filter_has_images')

    search = filters.CharFilter(method='filter_search')

    class Meta:
        model = Project
        fields = {
            'profile': ['exact'],
            'start_date': ['exact', 'gte', 'lte'],
        }

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )

    def filter_has_link(self, queryset, name, value):
        if value is None:
            return queryset
        if value:
            return queryset.exclude(Q(link__isnull=True) | Q(link__exact=''))
        else:
            return queryset.filter(Q(link__isnull=True) | Q(link__exact=''))

    def filter_has_images(self, queryset, name, value):
        if value is None:
            return queryset
        if value:
            return queryset.filter(images__isnull=False).distinct()
        else:
            return queryset.filter(images__isnull=True)


class EducationFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Education.
    """
    name_contains = filters.CharFilter(field_name='name', lookup_expr='icontains')
    diploma_contains = filters.CharFilter(field_name='diploma', lookup_expr='icontains')
    speciality_contains = filters.CharFilter(field_name='speciality', lookup_expr='icontains')

    year_min = filters.NumberFilter(field_name='year_of_graduation', lookup_expr='gte')
    year_max = filters.NumberFilter(field_name='year_of_graduation', lookup_expr='lte')

    profile_user_email = filters.CharFilter(field_name='profile__user__email', lookup_expr='icontains')

    search = filters.CharFilter(method='filter_search')

    class Meta:
        model = Education
        fields = {
            'profile': ['exact'],
            'year_of_graduation': ['exact', 'gte', 'lte'],
        }

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(diploma__icontains=value) |
            Q(speciality__icontains=value)
        )


class LanguageFilterSet(filters.FilterSet):
    """
    FilterSet pour le modèle Language.
    """
    name_contains = filters.CharFilter(field_name='name', lookup_expr='icontains')
    name_exact = filters.CharFilter(field_name='name', lookup_expr='iexact')

    level_min = filters.NumberFilter(field_name='level', lookup_expr='gte')
    level_max = filters.NumberFilter(field_name='level', lookup_expr='lte')
    level_range = filters.RangeFilter(field_name='level')

    profile_user_email = filters.CharFilter(field_name='profile__user__email', lookup_expr='icontains')
    profile_user_name = filters.CharFilter(method='filter_by_profile_user_name')

    search = filters.CharFilter(method='filter_search')

    order_by = filters.OrderingFilter(
        fields=(
            ('name', 'name'),
            ('level', 'level'),
            ('created_at', 'created_at'),
            ('profile__user__first_name', 'user_name'),
        ),
        field_labels={
            'name': 'Nom de la langue',
            'level': 'Niveau',
            'created_at': 'Date de création',
            'user_name': 'Nom utilisateur',
        }
    )

    class Meta:
        model = Language
        fields = {
            'profile': ['exact'],
            'level': ['exact', 'gte', 'lte'],
            'name': ['exact', 'icontains'],
        }

    def filter_by_profile_user_name(self, queryset, name, value):
        """Filtre par nom ou prénom de l'utilisateur du profil"""
        if not value:
            return queryset
        return queryset.filter(
            Q(profile__user__first_name__icontains=value) |
            Q(profile__user__last_name__icontains=value)
        )

    def filter_search(self, queryset, name, value):
        """Recherche globale dans le nom de la langue"""
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
        )
