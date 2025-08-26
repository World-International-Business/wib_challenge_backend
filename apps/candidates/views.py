from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.candidates.filters import (
    CandidateProfileFilterSet, ExperienceFilterSet, EducationFilterSet, ProjectFilterSet, LanguageFilterSet
)
from apps.candidates.models import CandidateProfile, Experience, Education, Language, Project, ProfileTechnology
from apps.candidates.serializers import CandidateProfileSerializer, ExperienceSerializer, EducationSerializer, \
    LanguageSerializer, ProjectSerializer, ProfileTechnologySerializer
from wib_challenge.permissions import IsOwner, ReadOnly


@extend_schema(
    tags=["Profil Candidats/Professionels"]
)
class CandidateProfileViewSet(viewsets.ModelViewSet):
    queryset = (CandidateProfile.objects
                .prefetch_related('profile_technologies', 'profession')
                .select_related('user').all()
                )
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwner | ReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CandidateProfileFilterSet
    search_fields = [
        'user__first_name', 'user__last_name', 'user__email',
        'location', 'short_bio', 'biography', 'interested_by',
        'profession__title'
    ]
    ordering_fields = [
        'created_at', 'updated_at', 'years_experience',
        'highest_degree', 'user__first_name', 'profession__title'
    ]
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user__is_staff=False, user__is_active=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path=r'user/(?P<user_id>\d+)')
    def get_by_user(self, request, user_id: int):
        profile = get_object_or_404(self.get_queryset(), user=user_id)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)


@extend_schema(
    tags=["Profil Candidats/Professionels"]
)
class NestedProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwner | ReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        get_object_or_404(CandidateProfile, pk=self.kwargs['profile_pk'])
        return self.queryset.filter(profile=self.kwargs['profile_pk'])

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


class ProfileTechnologyViewSet(NestedProfileViewSet):
    queryset = ProfileTechnology.objects.all()
    serializer_class = ProfileTechnologySerializer
    ordering = ['-level']


class ExperienceViewSet(NestedProfileViewSet):
    queryset = Experience.objects.select_related('profile__user').all()
    serializer_class = ExperienceSerializer

    filterset_class = ExperienceFilterSet
    search_fields = [
        'title', 'company', 'description', 'location'
    ]
    ordering_fields = [
        'start_date', 'end_date', 'title', 'company', 'created_at'
    ]
    ordering = ['-start_date', '-end_date']


class EducationViewSet(NestedProfileViewSet):
    queryset = Education.objects.select_related('profile__user').all()
    serializer_class = EducationSerializer

    filterset_class = EducationFilterSet
    search_fields = [
        'name', 'diploma', 'speciality'
    ]
    ordering_fields = [
        'year_of_graduation', 'name', 'diploma', 'created_at'
    ]
    ordering = ['-year_of_graduation', 'name']


class LanguageViewSet(NestedProfileViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer

    filterset_class = LanguageFilterSet
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'created_at']
    ordering = ['name']


class ProjectViewSet(NestedProfileViewSet):
    queryset = Project.objects.prefetch_related('images').select_related('profile__user').all()
    serializer_class = ProjectSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    filterset_class = ProjectFilterSet
    search_fields = [
        'name', 'description'
    ]
    ordering_fields = [
        'start_date', 'name', 'created_at'
    ]
    ordering = ['-start_date', 'name']


@extend_schema(
    parameters=[
        OpenApiParameter(name='project_id', type=int),
    ],
    tags=["Profil Candidats/Professionels"]
)
class ProjectImageViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    parser_classes = [MultiPartParser, FormParser]

    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        project_id = self.request.GET.get('project_id', None)
        if project_id:
            return self.queryset.filter(project_id=project_id)
        return super().get_queryset()
