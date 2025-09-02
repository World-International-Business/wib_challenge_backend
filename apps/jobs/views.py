from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, filters, status, mixins
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response

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


@extend_schema(tags=['Offres d\'emploi'])
class JobCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les catégories d'emploi (lecture seule)
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
