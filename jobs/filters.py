from django_filters import rest_framework as filters

from organizations.models import ExperienceLevel
from .models import JobOffer, JobCategory


class JobOfferFilter(filters.FilterSet):
    category = filters.ModelChoiceFilter(
        queryset=JobCategory.objects.all(),
        field_name='category',
        to_field_name='slug'
    )

    location = filters.CharFilter(
        field_name='location',
        lookup_expr='icontains'
    )

    company = filters.CharFilter(
        field_name='company__name',
        lookup_expr='icontains'
    )

    salary_min = filters.NumberFilter(
        field_name='salary_min',
        lookup_expr='gte'
    )

    salary_max = filters.NumberFilter(
        field_name='salary_max',
        lookup_expr='lte'
    )

    remote_allowed = filters.BooleanFilter(
        field_name='remote_allowed'
    )

    experience_level = filters.ChoiceFilter(
        choices=ExperienceLevel.choices,
        field_name='experience_level'
    )

    job_type = filters.ChoiceFilter(
        choices=JobOffer.JobType.choices,
        field_name='job_type'
    )

    published_after = filters.DateTimeFilter(
        field_name='published_at',
        lookup_expr='gte'
    )

    published_before = filters.DateTimeFilter(
        field_name='published_at',
        lookup_expr='lte'
    )

    class Meta:
        model = JobOffer
        fields = [
            'category', 'location', 'company', 'salary_min', 'salary_max',
            'remote_allowed', 'experience_level', 'job_type', 'status',
            'featured', 'published_after', 'published_before'
        ]
