from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .filters import JobOfferFilter
from .models import JobCategory, JobOffer
from .permissions import IsCompanyOwnerOrReadOnly
from .serializers import (
    JobCategorySerializer, JobCategoryListSerializer,
    JobOfferListSerializer, JobOfferDetailSerializer,
    JobOfferCreateUpdateSerializer
)


class JobCategoryViewSet(ReadOnlyModelViewSet):
    """
    ViewSet pour les catégories d'emploi (lecture seule)
    """
    queryset = JobCategory.objects.annotate(
        job_count=Count('job_offers', filter=Q(job_offers__status='published'))
    )
    serializer_class = JobCategorySerializer
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'list':
            return JobCategoryListSerializer
        return JobCategorySerializer


class JobOfferViewSet(ModelViewSet):
    """
    ViewSet pour les offres d'emploi avec toutes les opérations CRUD
    """
    queryset = JobOffer.objects.select_related('company', 'category')
    permission_classes = [IsAuthenticatedOrReadOnly, IsCompanyOwnerOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobOfferFilter
    search_fields = ['title', 'description', 'company__name', 'location']
    ordering_fields = ['created_at', 'published_at', 'salary_min', 'salary_max']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status='published')

        elif hasattr(self.request.user, 'organization'):
            queryset = queryset.filter(
                Q(company=self.request.user.organization) |
                Q(status='published')
            )

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return JobOfferListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return JobOfferCreateUpdateSerializer
        return JobOfferDetailSerializer

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.organization)

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
    def publish(self, request, slug=None):
        """Publier une offre d'emploi"""
        job = self.get_object()
        job.status = JobOffer.Status.PUBLISHED
        job.published_at = timezone.now()
        job.save()

        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, slug=None):
        """Dépublier une offre d'emploi"""
        job = self.get_object()
        job.status = JobOffer.Status.DRAFT
        job.save()

        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_filled(self, request, slug=None):
        """Marquer une offre comme fermée"""
        job = self.get_object()
        job.status = JobOffer.Status.FILLED
        job.save()

        serializer = self.get_serializer(job)
        return Response(serializer.data)


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
