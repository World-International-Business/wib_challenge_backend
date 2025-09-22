from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from apps.organizations.models import Organization
from .models import JobCategory, JobOffer, JobApplication
from ..core.models import Technology


class JobCategorySerializer(serializers.ModelSerializer):
    job_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = JobCategory
        fields = "__all__"
        read_only_fields = ['slug']


class JobCategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ['id', 'title', 'slug']


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
    skills = serializers.SlugRelatedField(slug_field='name', read_only=True, many=True)

    class Meta:
        model = JobOffer
        fields = [
            'id', 'title', 'slug', 'company', 'category', 'description',
            'responsibilities', 'requirements', 'benefits', 'salary_min',
            'salary_max', 'currency', 'job_type', 'experience_level',
            'location', 'remote_allowed', 'application_url', 'application_email',
            'status', 'featured', 'created_at', 'updated_at', 'published_at',
            'expires_at', 'skills'
        ]


class JobOfferCreateUpdateSerializer(WritableNestedModelSerializer):
    skills = serializers.SlugRelatedField(slug_field='name', many=True, queryset=Technology.objects.all())

    class Meta:
        model = JobOffer
        fields = [
            'title', 'category', 'description', 'responsibilities',
            'requirements', 'benefits', 'salary_min', 'salary_max',
            'currency', 'job_type', 'experience_level', 'location',
            'remote_allowed', 'application_url', 'application_email',
            'status', 'featured', 'expires_at', 'skills'
        ]

    def validate(self, data):
        if data.get('salary_min') and data.get('salary_max'):
            if data['salary_min'] > data['salary_max']:
                raise serializers.ValidationError(
                    "Le salaire minimum ne peut pas être supérieur au salaire maximum"
                )
        return data


class GenerateJobOfferSerializer(serializers.ModelSerializer):
    prompt = serializers.CharField(write_only=True)
    analyze = serializers.CharField(read_only=True)
    skills = serializers.SlugRelatedField(slug_field='name', many=True, queryset=Technology.objects.all())

    class Meta:
        model = JobOffer
        fields = ['title', 'description', 'responsibilities',
                  'requirements', 'benefits', 'prompt', 'analyze', 'skills']
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
            'responsibilities': {'required': False},
            'requirements': {'required': False},
            'benefits': {'required': False},
            'skills': {'required': False}
        }

    def validate_skills(self, skills):
        if not skills:
            return []

        matched_skills = []
        for skill in skills:
            matched_skill = Technology.objects.filter(name__icontains=skill).first()
            if matched_skill:
                matched_skills.append(matched_skill.name)
        return list(set(matched_skills))


class JobApplicationSerializer(serializers.ModelSerializer):
    use_profile = serializers.BooleanField(required=False)

    class Meta:
        model = JobApplication
        fields = '__all__'
        extra_kwargs = {
            'ai_analysis': {'read_only': True},
            'ai_decision': {'read_only': True},
            'job_offer': {'required': False},
            'user': {'required': False}
        }

    def validate(self, attrs):
        if not attrs.get('use_profile') and not attrs.get('resume'):
            raise serializers.ValidationError('Vous devez fournir un cv ou un profil')
        if attrs.get('use_profile') and attrs.get('resume'):
            raise serializers.ValidationError('Vous ne pouvez pas fournir un cv et un profil')
        attrs.pop('use_profile')
        return attrs


class JobMatchRequestSerializer(serializers.Serializer):
    """Schéma réduit d'une offre d'emploi pour l'endpoint /jobs/match."""
    title = serializers.CharField()
    description = serializers.CharField()
    responsibilities = serializers.CharField()
    requirements = serializers.CharField()
    benefits = serializers.CharField()
    # Le service de match accepte n'importe quelle chaîne pour jobType
    jobType = serializers.CharField(required=False, allow_blank=True, default="")
    experienceLevel = serializers.CharField(required=False, allow_blank=True, default="")
    location = serializers.CharField()
    remoteAllowed = serializers.BooleanField(required=False, default=False)
    featured = serializers.BooleanField(required=False, default=False)
    skills = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False, default=list)
