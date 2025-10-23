from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from apps.organizations.models import Organization
from .models import JobCategory, JobOffer, JobApplication
from ..core.models import Technology
from ..core.serializers import TagsSerializerField


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
    poste = JobCategoryListSerializer(read_only=True)
    applicants_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JobOffer
        fields = [
            'id', 'title', 'slug', 'company', 'poste', 'job_type',
            'experience_level', 'location', 'remote_allowed', 'salary',
            'currency', 'featured', 'published_at','expires_at','status','updated_at','skills',
            'attachments', 'required_documents', 'applicants_count'
        ]

    def get_applicants_count(self, obj):
        """Retourne le nombre de candidatures pour cette offre"""
        return obj.applications.count()


class JobOfferDetailSerializer(serializers.ModelSerializer):
    company = OrganizationBasicSerializer(read_only=True)
    poste = JobCategorySerializer(read_only=True)
    skills = serializers.SlugRelatedField(slug_field='name', read_only=True, many=True)

    class Meta:
        model = JobOffer
        fields = [
            'id', 'title', 'slug', 'company', 'poste', 'description',
            'responsibilities', 'requirements', 'benefits', 'salary',
            'currency', 'job_type', 'experience_level',
            'location', 'remote_allowed', 'application_url', 'application_email',
            'status', 'featured', 'created_at', 'updated_at', 'published_at',
            'expires_at', 'skills', 'attachments', 'required_documents'
        ]


class JobOfferCreateUpdateSerializer(WritableNestedModelSerializer):
    skills = TagsSerializerField(slug_field='name', many=True, queryset=Technology.objects.all())

    class Meta:
        model = JobOffer
        fields = [
            'title', 'poste', 'description', 'responsibilities',
            'requirements', 'benefits', 'salary',
            'currency', 'job_type', 'experience_level', 'location',
            'remote_allowed', 'application_url', 'application_email',
            'status', 'featured', 'expires_at', 'skills', 'attachments', 'required_documents'
        ]


class GenerateJobOfferSerializer(serializers.ModelSerializer):
    prompt = serializers.CharField(write_only=True)
    analyze = serializers.CharField(read_only=True)
    skills = TagsSerializerField(slug_field='name', many=True, queryset=Technology.objects.all(), required=False)

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



class JobApplicationSerializer(serializers.ModelSerializer):
    use_profile = serializers.BooleanField(required=False, write_only=True)
    profession = serializers.SerializerMethodField(read_only=True)
    location = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JobApplication
        fields = '__all__'
        extra_kwargs = {
            'ai_analysis': {'read_only': True},
            'ai_decision': {'read_only': True},
            'job_offer': {'required': False},
            'user': {'required': False}
        }

    def get_profession(self, obj):
        """Retourne la profession du candidat depuis son profil"""
        if obj.user and hasattr(obj.user, 'profile'):
            return obj.user.profile.profession.title if obj.user.profile.profession else None
        return None

    def get_location(self, obj):
        """Retourne l'adresse du candidat depuis son profil"""
        if obj.user and hasattr(obj.user, 'profile'):
            return obj.user.profile.location
        return None

    def validate(self, attrs):
        if not attrs.get('use_profile') and not attrs.get('resume'):
            raise serializers.ValidationError('Vous devez fournir un cv ou un profil')
        if attrs.get('use_profile') and attrs.get('resume'):
            raise serializers.ValidationError('Vous ne pouvez pas fournir un cv et un profil')
        attrs.pop('use_profile', None)
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
