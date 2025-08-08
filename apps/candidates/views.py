from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, extend_schema_view
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
from apps.candidates.models import CandidateProfile, Experience, Education, Language, Project
from apps.candidates.serializers import CandidateProfileSerializer, ExperienceSerializer, EducationSerializer, \
    LanguageSerializer, ProjectSerializer
from wib_challenge.permissions import IsOwner, ReadOnly


@extend_schema_view(
    list=extend_schema(
        summary="Liste des profils candidats",
        description="Récupère la liste paginée des profils de candidats avec filtres et recherche",
        tags=["Profils candidats"]
    ),
    create=extend_schema(
        summary="Créer un profil candidat",
        description="Crée un nouveau profil candidat pour l'utilisateur connecté",
        tags=["Profils candidats"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un profil candidat",
        description="Récupère les détails complets d'un profil candidat",
        tags=["Profils candidats"]
    ),
    update=extend_schema(
        summary="Mettre à jour un profil candidat",
        description="Met à jour complètement un profil candidat",
        tags=["Profils candidats"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'un profil candidat",
        description="Met à jour partiellement un profil candidat",
        tags=["Profils candidats"]
    ),
    destroy=extend_schema(
        summary="Supprimer un profil candidat",
        description="Supprime un profil candidat",
        tags=["Profils candidats"]
    )
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

    @extend_schema(
        summary="Profil par utilisateur",
        description="Récupère le profil candidat d'un utilisateur spécifique",
        tags=["Profils candidats"]
    )
    @action(detail=False, methods=['get'], url_path=r'user/(?P<user_id>\d+)')
    def get_by_user(self, request, user_id: int):
        profile = get_object_or_404(self.get_queryset(), user=user_id)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)


class NestedProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwner | ReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        get_object_or_404(CandidateProfile, pk=self.kwargs['profile_pk'])
        return self.queryset.filter(profile=self.kwargs['profile_pk'])

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des expériences",
        description="Récupère les expériences professionnelles d'un profil candidat",
        tags=["Expériences professionnelles"]
    ),
    create=extend_schema(
        summary="Ajouter une expérience",
        description="Ajoute une nouvelle expérience professionnelle au profil",
        tags=["Expériences professionnelles"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une expérience",
        description="Récupère les détails d'une expérience professionnelle",
        tags=["Expériences professionnelles"]
    ),
    update=extend_schema(
        summary="Mettre à jour une expérience",
        description="Met à jour une expérience professionnelle",
        tags=["Expériences professionnelles"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'une expérience",
        description="Met à jour partiellement une expérience professionnelle",
        tags=["Expériences professionnelles"]
    ),
    destroy=extend_schema(
        summary="Supprimer une expérience",
        description="Supprime une expérience professionnelle",
        tags=["Expériences professionnelles"]
    )
)
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


@extend_schema_view(
    list=extend_schema(
        summary="Liste des formations",
        description="Récupère les formations d'un profil candidat",
        tags=["Formations"]
    ),
    create=extend_schema(
        summary="Ajouter une formation",
        description="Ajoute une nouvelle formation au profil",
        tags=["Formations"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une formation",
        description="Récupère les détails d'une formation",
        tags=["Formations"]
    ),
    update=extend_schema(
        summary="Mettre à jour une formation",
        description="Met à jour une formation",
        tags=["Formations"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'une formation",
        description="Met à jour partiellement une formation",
        tags=["Formations"]
    ),
    destroy=extend_schema(
        summary="Supprimer une formation",
        description="Supprime une formation",
        tags=["Formations"]
    )
)
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


@extend_schema_view(
    list=extend_schema(
        summary="Liste des langues",
        description="Récupère les compétences linguistiques d'un profil candidat",
        tags=["Compétences linguistiques"]
    ),
    create=extend_schema(
        summary="Ajouter une langue",
        description="Ajoute une nouvelle compétence linguistique au profil",
        tags=["Compétences linguistiques"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une langue",
        description="Récupère les détails d'une compétence linguistique",
        tags=["Compétences linguistiques"]
    ),
    update=extend_schema(
        summary="Mettre à jour une langue",
        description="Met à jour une compétence linguistique",
        tags=["Compétences linguistiques"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'une langue",
        description="Met à jour partiellement une compétence linguistique",
        tags=["Compétences linguistiques"]
    ),
    destroy=extend_schema(
        summary="Supprimer une langue",
        description="Supprime une compétence linguistique",
        tags=["Compétences linguistiques"]
    )
)
class LanguageViewSet(NestedProfileViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer

    filterset_class = LanguageFilterSet
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'created_at']
    ordering = ['name']


@extend_schema_view(
    list=extend_schema(
        summary="Liste des projets",
        description="Récupère les projets d'un profil candidat",
        tags=["Projets"]
    ),
    create=extend_schema(
        summary="Ajouter un projet",
        description="Ajoute un nouveau projet au profil",
        tags=["Projets"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un projet",
        description="Récupère les détails d'un projet",
        tags=["Projets"]
    ),
    update=extend_schema(
        summary="Mettre à jour un projet",
        description="Met à jour un projet",
        tags=["Projets"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'un projet",
        description="Met à jour partiellement un projet",
        tags=["Projets"]
    ),
    destroy=extend_schema(
        summary="Supprimer un projet",
        description="Supprime un projet",
        tags=["Projets"]
    )
)
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
    summary="Images de projets",
    description="Gestion des images associées aux projets",
    tags=["Projets"]
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
