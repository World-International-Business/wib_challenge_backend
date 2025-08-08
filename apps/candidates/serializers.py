from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.candidates.models import (
    CandidateProfile, Experience, ProfileTechnology, Education, Language, Project, ProjectImage
)
from apps.core.models import Profession, Technology


class ProfileTechnologySerializer(serializers.ModelSerializer):
    name = serializers.SlugRelatedField(slug_field='name', queryset=Technology.objects, source='technology')

    class Meta:
        model = ProfileTechnology
        exclude = ('profile', 'technology')


class CandidateProfileSerializer(serializers.ModelSerializer):
    profession = serializers.SlugRelatedField(slug_field='title', queryset=Profession.objects)
    user = serializers.HyperlinkedRelatedField(view_name='accounts:users-detail', read_only=True)
    technologies = ProfileTechnologySerializer(many=True, source='profile_technologies', required=False)

    class Meta:
        model = CandidateProfile
        fields = '__all__'

    def create(self, validated_data):
        if hasattr(self.context['request'].user, 'profile'):
            raise serializers.ValidationError(_('You already have a profile'))
        technologies = validated_data.pop('profile_technologies', [])
        profile = super().create(validated_data)
        for technology in technologies:
            ProfileTechnology.objects.create(profile=profile, **technology)
        return profile

    def update(self, instance, validated_data):
        technologies = validated_data.pop('profile_technologies', [])
        instance = super().update(instance, validated_data)
        instance.profile_technologies.all().delete()
        for technology in technologies:
            ProfileTechnology.objects.create(profile=instance, **technology)
        return instance


class ProjectSerializer(serializers.ModelSerializer):
    images = serializers.SlugRelatedField(slug_field='image', many=True, read_only=True)
    pictures = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Project
        read_only_fields = ['profile']
        fields = '__all__'

    def create(self, validated_data):
        pictures = validated_data.pop('pictures', [])
        project = Project.objects.create(**validated_data)
        for picture in pictures:
            project.images.create(image=picture)
        return project


class ProjectImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectImage
        fields = '__all__'


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        read_only_fields = ['profile']
        fields = '__all__'


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        read_only_fields = ['profile']
        fields = '__all__'


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        read_only_fields = ['profile']
        fields = '__all__'
