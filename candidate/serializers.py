from rest_framework import serializers

from candidate.models import (
    CandidateProfile, Experience, ProfileTechnology, Education, Language, Project, ProjectImage
)
from core.models import Profession


class ProfileTechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileTechnology
        fields = '__all__'


class CandidateProfileSerializer(serializers.ModelSerializer):
    profession = serializers.SlugRelatedField(slug_field='title', queryset=Profession.objects.all())
    user = serializers.HyperlinkedRelatedField(view_name='accounts:user-detail', read_only=True)
    technologies = ProfileTechnologySerializer(many=True)

    class Meta:
        model = CandidateProfile
        fields = '__all__'

    def create(self, validated_data):
        technologies = validated_data.pop('technologies', [])
        profile = CandidateProfile.objects.create(**validated_data)
        for technology in technologies:
            ProfileTechnology.objects.create(profile=profile, **technology)
        return profile

    def update(self, instance, validated_data):
        technologies = validated_data.pop('technologies', [])
        instance = super().update(instance, validated_data)
        instance.technologies.all().delete()
        for technology in technologies:
            ProfileTechnology.objects.create(profile=instance, **technology)
        return instance


class ProjectSerializer(serializers.ModelSerializer):
    images = serializers.SlugRelatedField(slug_field='images', many=True, read_only=True)
    pictures = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Project
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
        fields = '__all__'


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = '__all__'


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = '__all__'
