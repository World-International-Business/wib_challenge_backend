from rest_framework import serializers
from .models import JobCategory, JobOffer
from organizations.models import Organization


class JobCategorySerializer(serializers.ModelSerializer):
    job_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = JobCategory
        fields = ['id', 'name', 'slug', 'description', 'job_count']
        read_only_fields = ['slug']


class JobCategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ['id', 'name', 'slug']


class OrganizationBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'logo', 'city', 'country']


class JobOfferListSerializer(serializers.ModelSerializer):
    company = OrganizationBasicSerializer(read_only=True)
    category = JobCategoryListSerializer(read_only=True)

    class Meta:
        model = JobOffer
        fields = [
            'id', 'title', 'slug', 'company', 'category', 'job_type',
            'experience_level', 'location', 'remote_allowed', 'salary_min',
            'salary_max', 'currency', 'featured', 'published_at'
        ]


class JobOfferDetailSerializer(serializers.ModelSerializer):
    company = OrganizationBasicSerializer(read_only=True)
    category = JobCategorySerializer(read_only=True)

    class Meta:
        model = JobOffer
        fields = [
            'id', 'title', 'slug', 'company', 'category', 'description',
            'responsibilities', 'requirements', 'benefits', 'salary_min',
            'salary_max', 'currency', 'job_type', 'experience_level',
            'location', 'remote_allowed', 'application_url', 'application_email',
            'status', 'featured', 'created_at', 'updated_at', 'published_at',
            'expires_at'
        ]


class JobOfferCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobOffer
        fields = [
            'title', 'category', 'description', 'responsibilities',
            'requirements', 'benefits', 'salary_min', 'salary_max',
            'currency', 'job_type', 'experience_level', 'location',
            'remote_allowed', 'application_url', 'application_email',
            'status', 'featured', 'expires_at'
        ]

    def validate(self, data):
        if data.get('salary_min') and data.get('salary_max'):
            if data['salary_min'] > data['salary_max']:
                raise serializers.ValidationError(
                    "Le salaire minimum ne peut pas être supérieur au salaire maximum"
                )
        return data
