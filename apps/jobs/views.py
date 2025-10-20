from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import generics, filters, status, mixins
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
import os
import json
from urllib.parse import quote
import requests

from services.cv_analyzer import analyze_job_application
from services.generate_offer import generate_offer
from services.users_job_suggestions import get_users_suggestions_for_job
from wib_challenge.pagination import paginated_response
from wib_challenge.permissions import ReadOnly
from .filters import JobOfferFilter, JobApplicationFilter
from .models import JobCategory, JobOffer, JobApplication
from .permissions import IsCompanyOwnerOrReadOnly
from .serializers import (
    JobCategorySerializer, JobCategoryListSerializer,
    JobOfferListSerializer, JobOfferDetailSerializer,
    JobOfferCreateUpdateSerializer, GenerateJobOfferSerializer, JobApplicationSerializer
)
from ..accounts.permissions import IsOrganization
from ..accounts.serializers import UserSerializer
from .serializers import JobMatchRequestSerializer
from apps.accounts.models import User


@extend_schema(tags=['Offres d\'emploi'])
class JobCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les catégories d'emploi (lecture seule uniquement)
    """
    queryset = JobCategory.objects.annotate(
        job_count=Count('job_offers', filter=Q(job_offers__status='published'))
    )
    serializer_class = JobCategorySerializer
    permission_classes = [IsAdminUser | IsOrganization | ReadOnly]

    def get_serializer_class(self):
        if self.action == 'list':
            return JobCategoryListSerializer
        return JobCategorySerializer


@extend_schema(tags=['Offres d\'emploi'])
class JobOfferViewSet(viewsets.ModelViewSet):
    """
      ViewSet pour les offres d'emploi avec toutes les opérations CRUD
    """
    queryset = JobOffer.objects.select_related('company', 'category')
    permission_classes = [IsAuthenticatedOrReadOnly, IsCompanyOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobOfferFilter
    search_fields = ['title', 'description', 'company__name', 'location']
    ordering_fields = ['created_at', 'published_at', 'salary_min', 'salary_max']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        if hasattr(self.request.user, 'organization'):
            queryset = queryset.filter(
                Q(company=self.request.user.organization) |
                Q(status=JobOffer.Status.PUBLISHED)
            )
        else:
            queryset = queryset.filter(status=JobOffer.Status.PUBLISHED)

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return JobOfferListSerializer
        elif self.action == 'generate':
            return GenerateJobOfferSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return JobOfferCreateUpdateSerializer
        return JobOfferDetailSerializer

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.organization)
    
    @action(detail=False, methods=['get'], url_path='slug/<slug:slug>/')
    def get_by_slug(self, request, slug=None):
        """Récupérer une offre d'emploi par son slug"""
        job = self.get_queryset().filter(slug=slug).first()
        if not job:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance=job)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Récupérer les offres d'emploi mises en avant"""
        featured_jobs = self.get_queryset().filter(
            featured=True,
            status='published'
        ).order_by('-published_at')

        page = self.paginate_queryset(featured_jobs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(featured_jobs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Récupérer les offres d'emploi récentes"""
        recent_jobs = self.get_queryset().filter(
            status='published'
        ).order_by('-published_at')

        page = self.paginate_queryset(recent_jobs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(recent_jobs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publier une offre d'emploi"""
        job = self.get_object()
        job.status = JobOffer.Status.PUBLISHED
        job.published_at = job.published_at or timezone.now()
        job.save()

        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """Dépublier une offre d'emploi"""
        job = self.get_object()
        job.status = JobOffer.Status.DRAFT
        job.published_at = None
        job.save()

        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_filled(self, request, pk=None):
        """Marquer une offre comme fermée"""
        job = self.get_object()
        job.status = JobOffer.Status.FILLED
        job.save()

        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @extend_schema(
        request=GenerateJobOfferSerializer,
        responses={200: GenerateJobOfferSerializer}
    )
    @action(detail=False, methods=['post'])
    def generate(self, request):
        serializer = GenerateJobOfferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            prompt_description = serializer.validated_data.pop('prompt')
            data = generate_offer(prompt_description, serializer.validated_data)
            serializer = GenerateJobOfferSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            return Response({**data, **serializer.validated_data})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @extend_schema(
        request=JobApplicationSerializer,
        responses={200: JobApplicationSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[])
    def apply(self, request, pk=None):
        """
        Permet à un candidat de postuler une offre d'emploi.
        """
        job_offer = self.get_object()
        serializer = JobApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated and hasattr(request.user, 'profile') else None
        serializer.save(job_offer=job_offer, user=user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        parameters=[
            OpenApiParameter(name='application_id', type=int, location=OpenApiParameter.PATH)
        ],
        responses={200: JobApplicationSerializer}
    )
    @action(detail=True, methods=['post'], url_path='analyze/<int:application_id>')
    def analyze(self, request, pk=None, application_id=None):
        """
        Permet à un candidat de postuler une offre d'emploi.
        """
        job_offer = self.get_object()
        job_application = get_object_or_404(job_offer.applications.all(), pk=application_id)
        job_application = analyze_job_application(job_application, job_offer)
        serializer = JobApplicationSerializer(instance=job_application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses=UserSerializer(many=True)
    )
    @action(detail=True, methods=['get'], url_path='suggest-users')
    def suggest_users(self, request, pk=None):
        users = get_users_suggestions_for_job(self.get_object())
        return paginated_response(self, users, UserSerializer)


@extend_schema(tags=['Offres d\'emploi'])
class MyJobOffersView(generics.ListAPIView):
    """
    Vue pour lister les offres d'emploi de l'organisation connectée
    """
    serializer_class = JobOfferListSerializer
    queryset = JobOffer.objects.none()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'job_type', 'experience_level']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'published_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return JobOffer.objects.filter(
            company=self.request.user.organization
        ).select_related('company', 'category')


@extend_schema(tags=['Offres d\'emploi'])
class JobSearchView(generics.ListAPIView):
    """
    Vue dédiée à la recherche d'offres d'emploi
    """
    serializer_class = JobOfferListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobOfferFilter
    search_fields = ['title', 'description', 'company__name', 'location', 'requirements']
    ordering_fields = ['created_at', 'published_at', 'salary_min', 'salary_max']
    ordering = ['-published_at']

    def get_queryset(self):
        return JobOffer.objects.filter(
            status='published'
        ).select_related('company', 'category')


@extend_schema(tags=['Offres d\'emploi'])
class JobApplicationViewSet(mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les applications d'emploi
    """
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobApplicationFilter
    permission_classes = [IsAuthenticated, IsOrganization]

    def get_queryset(self):
        if hasattr(self.request.user, 'organization'):
            return JobApplication.objects.filter(
                job_offer__company=self.request.user.organization
            ).select_related('job_offer', 'job_offer__company')
        else:
            return JobApplication.objects.none()


@extend_schema(tags=["Offres d'emploi"], request=JobMatchRequestSerializer)
class JobMatchView(GenericAPIView):
    """Endpoint /jobs/match qui relaye une requête vers le service FastAPI de matching.

    Il prend un JSON réduit décrivant l'offre et l'encode dans le path
    de la route externe: http://celeryfastapi-213-32-91-101.traefik.me/match/{json}
    """
    serializer_class = JobMatchRequestSerializer
    permission_classes = []

    MATCH_SERVICE_URL = os.getenv(
        "JOB_MATCH_SERVICE_URL",
        "http://api-celery-fastapi-213-32-91-101.traefik.me/",
        # "http://localhost:8001",
    )

    @extend_schema(
        summary="Match d'un job avec des candidats",
        description=(
            "Effectue un matching entre une offre d'emploi et des candidats. "
            "Retourne une liste de candidats avec leurs informations de contact et d'éventuelles erreurs."
        ),
        request=JobMatchRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Liste des candidats avec leurs informations de contact",
                response={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "candidateId": {"type": "string", "description": "Identifiant unique du candidat"},
                            "firstName": {"type": "string", "description": "Prénom du candidat"},
                            "lastName": {"type": "string", "description": "Nom de famille du candidat"},
                            "email": {"type": "string", "format": "email", "description": "Email du candidat"},
                            "phone": {"type": "string", "description": "Numéro de téléphone du candidat"},
                            "error": {"type": "string", "description": "Message d'erreur éventuel pour ce candidat"}
                        },
                        "required": ["candidateId", "firstName", "lastName", "email", "phone", "error"]
                    }
                }
            ),
            400: OpenApiResponse(description="Payload invalide"),
            502: OpenApiResponse(description="Erreur lors de l'appel au service externe"),
        },
        examples=[
            OpenApiExample(
                "Exemple de requête complète",
                value={
                    "title": "Senior Backend Engineer",
                    "description": "Développer des APIs scalables",
                    "responsibilities": "Concevoir, coder, tester",
                    "requirements": "5+ ans Python/Django",
                    "benefits": "Télétravail, BSPCE",
                    "jobType": "full_time",
                    "experienceLevel": "senior",
                    "location": "Paris",
                    "remoteAllowed": True,
                    "featured": True,
                    "skills": ["Python", "Django", "PostgreSQL"]
                },
                request_only=True
            ),
            OpenApiExample(
                "Exemple de réponse",
                value=[
                    {
                        "candidateId": "123e4567-e89b-12d3-a456-426614174000",
                        "firstName": "Jean",
                        "lastName": "Dupont",
                        "email": "jean.dupont@example.com",
                        "phone": "+33123456789",
                        "error": ""
                    },
                    {
                        "candidateId": "123e4567-e89b-12d3-a456-426614174001",
                        "firstName": "Marie",
                        "lastName": "Martin",
                        "email": "marie.martin@example.com",
                        "phone": "+33987654321",
                        "error": ""
                    }
                ],
                response_only=True
            )
        ],
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Construire le JSON pour le service externe
        payload = serializer.validated_data
        # Adapter aux exigences du service FastAPI (champ 'id' requis et 'required_skills')
        # L'API FastAPI attend id en chaîne: convertissons systématiquement
        inbound_id = request.data.get("id", "0")
        try:
            outbound_id = str(inbound_id)
        except Exception:
            outbound_id = "0"

        outbound = {
            **payload,
            "id": outbound_id,
            "required_skills": payload.get("skills", []),
        }
        url = f"{self.MATCH_SERVICE_URL}/match"
        try:
            resp = requests.post(url, json=outbound, timeout=200)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}
        else:
            data = {"raw": resp.text}

        # Si l'appel externe a échoué, renvoyer la réponse telle quelle
        if resp.status_code >= 400:
            return Response(data, status=resp.status_code)

        # Transformer la réponse (liste de {rank, candidateId, score}) en contacts candidats
        results = []
        items = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
        for item in items:
            try:
                # Supporter candidateId ou candidate_id
                cid_raw = None
                if isinstance(item, dict):
                    cid_raw = item.get("candidateId") if "candidateId" in item else item.get("candidate_id")
                cid_str = str(cid_raw) if cid_raw is not None else None

                if not cid_str:
                    results.append({
                        "candidateId": None,
                        "firstName": None,
                        "lastName": None,
                        "email": None,
                        "phone": None,
                        "error": "candidateId manquant"
                    })
                    continue

                user = User.objects.filter(pk=cid_str).first()
                if user is None:
                    results.append({
                        "candidateId": cid_str,
                        "firstName": None,
                        "lastName": None,
                        "email": None,
                        "phone": None,
                        "error": "candidat introuvable"
                    })
                else:
                    results.append({
                        "candidateId": str(user.id),
                        "firstName": user.first_name,
                        "lastName": user.last_name,
                        "email": user.email,
                        "phone": user.phone,
                    })
            except Exception as e:
                results.append({
                    "candidateId": None,
                    "firstName": None,
                    "lastName": None,
                    "email": None,
                    "phone": None,
                    "error": f"exception: {str(e)}"
                })

        return Response(results, status=status.HTTP_200_OK)
