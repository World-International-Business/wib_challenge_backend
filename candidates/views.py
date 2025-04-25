from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from candidates.models import CandidateProfile, Experience, Education, Language, Project
from candidates.serializers import CandidateProfileSerializer, ExperienceSerializer, EducationSerializer, \
    LanguageSerializer, ProjectSerializer
from wib_challenge.permissions import IsOwner, ReadOnly


class CandidateProfileViewSet(viewsets.ModelViewSet):
    queryset = (CandidateProfile.objects
                .prefetch_related('profile_technologies', 'profession')
                .select_related('user').all()
                )
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwner | ReadOnly]

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


class NestedProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwner | ReadOnly]

    def get_queryset(self):
        get_object_or_404(CandidateProfile, pk=self.kwargs['profile_pk'])
        return self.queryset.filter(profile=self.kwargs['profile_pk'])

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


class ExperienceViewSet(NestedProfileViewSet):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer


class EducationViewSet(NestedProfileViewSet):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer


class LanguageViewSet(NestedProfileViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer


class ProjectViewSet(NestedProfileViewSet):
    queryset = Project.objects.prefetch_related('images').all()
    serializer_class = ProjectSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]


@extend_schema(
    parameters=[
        OpenApiParameter(name='project_id', type=int),
    ]
)
class ProjectImageViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        project_id = self.request.GET.get('project_id', None)
        if project_id:
            return self.queryset.filter(project_id=project_id)
        return self.get_queryset()
