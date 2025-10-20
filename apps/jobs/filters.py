from django_filters import rest_framework as filters

from apps.evaluations.models import ExperienceLevel
from .models import JobOffer, JobCategory, JobApplication


class JobOfferFilter(filters.FilterSet):
    poste = filters.ModelChoiceFilter(
        queryset=JobCategory.objects.all(),
        field_name='poste',
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

    salary = filters.CharFilter(
        field_name='salary',
        lookup_expr='icontains'
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
            'poste', 'location', 'company', 'salary',
            'remote_allowed', 'experience_level', 'job_type', 'status',
            'featured', 'published_after', 'published_before'
        ]


class JobApplicationFilter(filters.FilterSet):
    status = filters.ChoiceFilter(
        choices=JobApplication.ApplicationStatus.choices,
        field_name='status'
    )
    
    job_offer = filters.NumberFilter(
        field_name='job_offer__id'
    )
    
    submitted_after = filters.DateTimeFilter(
        field_name='submitted_at',
        lookup_expr='gte'
    )
    
    submitted_before = filters.DateTimeFilter(
        field_name='submitted_at',
        lookup_expr='lte'
    )
    
    applicant_name = filters.CharFilter(
        field_name='applicant_name',
        lookup_expr='icontains'
    )
    
    applicant_email = filters.CharFilter(
        field_name='applicant_email',
        lookup_expr='icontains'
    )

    class Meta:
        model = JobApplication
        fields = ['job_offer', 'status', 'ai_decision', 'submitted_after', 'submitted_before', 
                  'applicant_name', 'applicant_email']
