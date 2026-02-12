from datetime import timedelta
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import generics, filters, status, mixins
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
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
from .models import JobCategory, JobOffer, JobApplication, JobApplicationEvaluation
from .permissions import IsCompanyOwnerOrReadOnly
from .serializers import (
    JobCategorySerializer, JobCategoryListSerializer,
    JobOfferListSerializer, JobOfferDetailSerializer,
    JobOfferCreateUpdateSerializer, GenerateJobOfferSerializer, JobApplicationSerializer,
    OrganizationApplicationSerializer,
)
from ..accounts.permissions import IsOrganization
from ..accounts.serializers import UserSerializer
from .serializers import JobMatchRequestSerializer
from apps.evaluations.models import Candidate, EvaluationInvitation, SubmissionAttempt, Participant
from apps.evaluations.utils import send_invitation_email
from apps.accounts.models import User
from apps.organizations.models import Notification, UserNotification


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
    queryset = JobOffer.objects.select_related('company', 'poste')
    permission_classes = [IsAuthenticatedOrReadOnly, IsCompanyOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobOfferFilter
    search_fields = ['title', 'description', 'company__name', 'location']
    ordering_fields = ['created_at', 'published_at', 'salary']
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
        Gère l'upload de documents dynamiques selon les required_documents de l'offre.
        """
        from django.core.files.storage import default_storage
        from rest_framework.exceptions import ValidationError as DRFValidationError
        
        job_offer = self.get_object()
        required_docs = job_offer.required_documents or []
        
        # Valider que tous les documents requis sont fournis
        doc_labels = {
            'portfolio': 'Portfolio',
            'diploma': 'Diplôme',
            'id_card': 'Pièce d\'identité',
            'work_permit': 'Permis de travail',
            'recommendation_letter': 'Lettre de recommandation',
            'certificate': 'Certificat professionnel',
            'transcript': 'Relevé de notes'
        }
        
        missing_docs = []
        for doc_type in required_docs:
            # CV et cover_letter sont gérés séparément par le serializer
            if doc_type in ['cv', 'cover_letter']:
                continue
            
            file_key = f'document_{doc_type}'
            if file_key not in request.FILES:
                label = doc_labels.get(doc_type, doc_type)
                missing_docs.append(label)
        
        if missing_docs:
            raise DRFValidationError({
                'detail': f'Documents manquants: {", ".join(missing_docs)}'
            })
        
        # Créer l'application
        serializer = JobApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated and hasattr(request.user, 'profile') else None
        application = serializer.save(job_offer=job_offer, user=user)
        
        # Uploader et sauvegarder les documents additionnels
        documents_saved = {}
        for doc_type in required_docs:
            if doc_type in ['cv', 'cover_letter']:
                continue
                
            file_key = f'document_{doc_type}'
            if file_key in request.FILES:
                uploaded_file = request.FILES[file_key]
                # Sauvegarder le fichier dans le dossier job_documents
                file_path = f'job_documents/{application.id}/{doc_type}_{uploaded_file.name}'
                saved_path = default_storage.save(file_path, uploaded_file)
                documents_saved[doc_type] = default_storage.url(saved_path)
        
        # Mettre à jour l'application avec les URLs des documents
        if documents_saved:
            application.documents = documents_saved
            application.save(update_fields=['documents'])

        # Analyse CV en arrière-plan (optionnel)
        if getattr(settings, 'USE_CELERY_FOR_CV_ANALYSIS', False):
            try:
                from apps.jobs.tasks import analyze_job_application_task

                analyze_job_application_task.delay(application.id)
            except Exception:
                # On ne bloque pas la candidature si Celery/Redis n'est pas disponible
                pass
        
        serializer = JobApplicationSerializer(instance=application)
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

    @extend_schema(
        request=None,
        responses={
            200: OpenApiResponse(
                description="Liste des candidatures avec statistiques",
                examples=[
                    OpenApiExample(
                        'Exemple de réponse',
                        value={
                            "statistics": {
                                "total": 25,
                                "pending": 15,
                                "shortlisted": 5,
                                "accepted": 3,
                                "rejected": 2
                            },
                            "applications": []
                        }
                    )
                ]
            )
        }
    )
    @action(detail=True, methods=['get'], url_path='applications')
    def get_applications(self, request, pk=None):
        """
        Récupère toutes les candidatures d'une offre avec statistiques par statut.
        Filtres disponibles: ?status=pending&applicant_name=John
        """
        job_offer = self.get_object()
        applications = job_offer.applications.select_related(
            'user', 
            'user__profile', 
            'user__profile__profession'
        ).all()
        
        # Appliquer les filtres
        filterset = JobApplicationFilter(request.GET, queryset=applications)
        filtered_applications = filterset.qs
        
        # Calculer les statistiques
        stats = applications.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            shortlisted=Count('id', filter=Q(status='shortlisted')),
            accepted=Count('id', filter=Q(status='accepted')),
            rejected=Count('id', filter=Q(status='rejected'))
        )
        
        # Sérialiser les candidatures filtrées
        serializer = JobApplicationSerializer(filtered_applications, many=True)
        
        return Response({
            'statistics': stats,
            'applications': serializer.data
        })

    @extend_schema(
        summary="(Re)lancer l'analyse CV / matching pour toutes les candidatures d'une offre",
        description=(
            "Déclenche l'analyse CV pour toutes les candidatures de l'offre. "
            "Si Celery est activé, les analyses sont queue en arrière-plan. "
            "Sinon, l'analyse est exécutée de manière synchrone (peut prendre du temps)."
        ),
        responses={
            200: OpenApiResponse(description="Résultat du batch (queued ou processed)")
        },
    )
    @action(detail=True, methods=['post'], url_path='applications/recompute')
    def recompute_applications(self, request, pk=None):
        job_offer = self.get_object()

        applications = job_offer.applications.select_related('job_offer').all()
        total = applications.count()

        failures = []
        queued = 0
        processed = 0

        if getattr(settings, 'USE_CELERY_FOR_CV_ANALYSIS', False):
            try:
                from apps.jobs.tasks import analyze_job_application_task

                for application in applications:
                    try:
                        analyze_job_application_task.delay(application.id)
                        queued += 1
                    except Exception as e:
                        failures.append({'application_id': application.id, 'error': str(e)})

                return Response(
                    {
                        'status': 'queued',
                        'total': total,
                        'processed': 0,
                        'queued': queued,
                        'failed': len(failures),
                        'failures': failures,
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {
                        'status': 'celery_error',
                        'detail': str(e),
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        # Fallback synchrone
        for application in applications:
            try:
                analyze_job_application(application, job_offer, save=True)
                processed += 1
            except Exception as e:
                failures.append({'application_id': application.id, 'error': str(e)})

        return Response(
            {
                'status': 'processed',
                'total': total,
                'processed': processed,
                'queued': 0,
                'failed': len(failures),
                'failures': failures,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Statistiques globales des offres d'emploi",
        description="Retourne les statistiques globales des offres d'emploi de l'organisation connectée",
        responses={
            200: OpenApiResponse(
                description="Statistiques des offres d'emploi",
                examples=[
                    OpenApiExample(
                        'Exemple de réponse',
                        value={
                            "total": 10,
                            "published": 8,
                            "draft": 2,
                            "candidates": 25
                        }
                    )
                ]
            )
        }
    )
    @action(detail=False, methods=['get'], url_path='my-stats')
    def my_stats(self, request):
        """
        Retourne les statistiques globales des offres d'emploi de l'organisation connectée
        """
        # Vérifier que l'utilisateur a une organisation
        if not hasattr(request.user, 'organization') or not request.user.organization:
            return Response(
                {'error': 'Utilisateur non associé à une organisation'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Statistiques des offres
        job_offers = JobOffer.objects.filter(company=request.user.organization)
        stats = job_offers.aggregate(
            total=Count('id'),
            published=Count('id', filter=Q(status='published')),
            draft=Count('id', filter=Q(status='draft')),
            expired=Count('id', filter=Q(status='expired')),
            filled=Count('id', filter=Q(status='filled'))
        )
        
        # Nombre total de candidatures
        total_candidates = JobApplication.objects.filter(
            job_offer__company=request.user.organization
        ).count()
        
        stats['candidates'] = total_candidates
        
        return Response(stats)

    @extend_schema(
        summary="Importer les candidats matchés",
        description=(
            "Appelle l'API de matching pour cette offre et crée automatiquement "
            "des candidatures pour chaque candidat matché. Les candidatures sont marquées "
            "avec source='matched' pour les différencier des candidatures spontanées."
        ),
        responses={
            200: OpenApiResponse(
                description="Liste des candidatures créées",
                examples=[
                    OpenApiExample(
                        'Exemple de réponse',
                        value={
                            "created": 5,
                            "skipped": 2,
                            "errors": 0,
                            "applications": []
                        }
                    )
                ]
            )
        }
    )
    @action(detail=True, methods=['post'], url_path='import-matched-candidates')
    def import_matched_candidates(self, request, pk=None):
        """
        Importe les candidats matchés pour cette offre en créant de vraies candidatures.
        """
        job_offer = self.get_object()
        
        # Préparer le payload pour l'API de matching
        skills_list = list(job_offer.skills.values_list('name', flat=True))
        payload = {
            "id": str(job_offer.id),
            "title": job_offer.title,
            "description": job_offer.description or "",
            "responsibilities": job_offer.responsibilities or "",
            "requirements": job_offer.requirements or "",
            "benefits": job_offer.benefits or "",
            "jobType": job_offer.job_type or "",
            "experienceLevel": job_offer.experience_level or "",
            "location": job_offer.location or "",
            "remoteAllowed": job_offer.remote_allowed,
            "featured": job_offer.featured,
            "skills": skills_list,
            "required_skills": skills_list,
        }
        
        # Appeler l'API de matching
        match_service_url = os.getenv(
            "JOB_MATCH_SERVICE_URL",
            "http://api-celery-fastapi-213-32-91-101.traefik.me/",
        )
        
        try:
            resp = requests.post(
                f"{match_service_url}/match",
                json=payload,
                timeout=200
            )
            resp.raise_for_status()
            matched_candidates = resp.json()
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de l\'appel à l\'API de matching: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        
        # Statistiques d'import
        created_count = 0
        skipped_count = 0
        error_count = 0
        created_applications = []
        
        # Traiter les candidats matchés
        items = matched_candidates if isinstance(matched_candidates, list) else matched_candidates.get("results", [])
        
        for item in items:
            try:
                # Récupérer l'ID du candidat
                candidate_id = item.get("candidateId") or item.get("candidate_id")
                if not candidate_id:
                    error_count += 1
                    continue
                
                # Récupérer l'utilisateur
                try:
                    user = User.objects.get(pk=candidate_id)
                except User.DoesNotExist:
                    error_count += 1
                    continue
                
                # Vérifier si une candidature existe déjà pour cet utilisateur et cette offre
                existing = JobApplication.objects.filter(
                    job_offer=job_offer,
                    user=user
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Créer la candidature avec source='matched'
                application = JobApplication.objects.create(
                    job_offer=job_offer,
                    user=user,
                    applicant_name=f"{user.first_name} {user.last_name}".strip() or user.email,
                    applicant_email=user.email,
                    source=JobApplication.ApplicationSource.MATCHED,
                    status=JobApplication.ApplicationStatus.PENDING,
                    cover_letter=f"Candidat matché automatiquement par le système de matching pour le poste {job_offer.title}.",
                )
                
                created_applications.append(application)
                created_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        # Sérialiser les candidatures créées
        serializer = JobApplicationSerializer(created_applications, many=True)
        
        return Response({
            'created': created_count,
            'skipped': skipped_count,
            'errors': error_count,
            'total_matched': len(items),
            'applications': serializer.data
        }, status=status.HTTP_201_CREATED)


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
        ).select_related('company', 'poste')


@extend_schema(tags=['Offres d\'emploi'])
class JobSearchView(generics.ListAPIView):
    """
    Vue dédiée à la recherche d'offres d'emploi
    """
    serializer_class = JobOfferListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobOfferFilter
    search_fields = ['title', 'description', 'company__name', 'location', 'requirements']
    ordering_fields = ['created_at', 'published_at', 'salary']
    ordering = ['-published_at']

    def get_queryset(self):
        return JobOffer.objects.filter(
            status='published'
        ).select_related('company', 'poste')


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
    search_fields = ['applicant_name', 'applicant_email']
    ordering_fields = ['submitted_at', 'status']
    ordering = ['-submitted_at']

    def get_queryset(self):
        if hasattr(self.request.user, 'organization'):
            return JobApplication.objects.filter(
                job_offer__company=self.request.user.organization
            ).select_related(
                'job_offer', 
                'job_offer__company', 
                'user',
                'user__profile',
                'user__profile__profession'
            )
        else:
            return JobApplication.objects.none()

    @extend_schema(
        summary="Lister toutes les candidatures de l'organisation",
        description=(
            "Retourne les candidatures de toutes les offres de l'organisation connectée, "
            "avec possibilité de filtrer par offre, source et recherche sur le nom/email candidat."
        ),
        parameters=[
            OpenApiParameter(name='organization', type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='job_offer', type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='source', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='search', type=str, location=OpenApiParameter.QUERY),
        ],
        responses={200: OrganizationApplicationSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='organization')
    def list_by_organization(self, request):
        """Endpoint `/jobs/applications/organization/` pour CvMails.

        Utilise l'organisation de l'utilisateur connecté comme source de vérité
        et applique les filtres demandés par le frontend.
        """
        from django.db.models import Q

        # Sécurité : l'utilisateur doit être lié à une organisation
        user_org = getattr(request.user, 'organization', None)
        if not user_org:
            return Response(
                {'detail': 'Utilisateur non associé à une organisation'},
                status=status.HTTP_403_FORBIDDEN,
            )

        org_param = request.query_params.get('organization')
        if org_param and str(org_param) != str(user_org.id):
            return Response(
                {'detail': "Vous ne pouvez consulter que les candidatures de votre organisation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = self.get_queryset()

        # Filtres supplémentaires
        job_offer_id = request.query_params.get('job_offer')
        source = request.query_params.get('source')
        search = request.query_params.get('search')

        if job_offer_id:
            queryset = queryset.filter(job_offer_id=job_offer_id)

        if source:
            queryset = queryset.filter(source=source)

        if search:
            queryset = queryset.filter(
                Q(applicant_name__icontains=search)
                | Q(applicant_email__icontains=search)
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = OrganizationApplicationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = OrganizationApplicationSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Lancer (ou relancer) l'analyse CV d'une candidature",
        description=(
            "Queue l'analyse CV en arrière-plan via Celery si activé. "
            "Si Celery n'est pas activé/disponible, l'endpoint renvoie une réponse explicite."
        ),
        responses={200: OpenApiResponse(description="Analyse queue ou non disponible")},
    )
    @action(detail=True, methods=['post'], url_path='analyze')
    def queue_analysis(self, request, pk=None):
        application = self.get_object()

        if not getattr(settings, 'USE_CELERY_FOR_CV_ANALYSIS', False):
            try:
                analyze_job_application(application, application.job_offer, save=True)
                return Response({'status': 'processed'}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(
                    {
                        'status': 'failed',
                        'detail': str(e),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        try:
            from apps.jobs.tasks import analyze_job_application_task

            analyze_job_application_task.delay(application.id)
            return Response({'status': 'queued'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {
                    'status': 'error',
                    'detail': str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        """
        Met à jour le statut d'une candidature et optionnellement les détails de recrutement.
        """
        application = self.get_object()
        new_status = request.data.get('status')
        recruitment_details = request.data.get('recruitment_details')
        
        if new_status not in dict(JobApplication.ApplicationStatus.choices):
            return Response(
                {'error': 'Statut invalide. Choix possibles: pending, shortlisted, accepted, rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = application.status
        application.status = new_status
        
        # Si des détails de recrutement sont fournis (pour le statut 'accepted')
        if recruitment_details:
            application.recruitment_details = recruitment_details
            application.save(update_fields=['status', 'recruitment_details', 'updated_at'])
        else:
            application.save(update_fields=['status', 'updated_at'])
        
        # Créer des notifications pour le candidat selon le nouveau statut
        if application.user and old_status != new_status:
            from apps.organizations.models import UserNotification
            
            if new_status == 'accepted':
                UserNotification.objects.create(
                    user=application.user,
                    type='application_accepted',
                    title=f"Félicitations ! Vous êtes recruté(e)",
                    message=f"Votre candidature pour le poste de {application.job_offer.title} a été acceptée. Bienvenue dans l'équipe !",
                    related_application=application
                )
            elif new_status == 'rejected':
                UserNotification.objects.create(
                    user=application.user,
                    type='application_rejected',
                    title=f"Candidature pour {application.job_offer.title}",
                    message=f"Malheureusement, votre candidature pour le poste de {application.job_offer.title} n'a pas été retenue cette fois-ci.",
                    related_application=application
                )
            elif new_status == 'shortlisted':
                UserNotification.objects.create(
                    user=application.user,
                    type='application_shortlisted',
                    title=f"Candidature présélectionnée",
                    message=f"Bonne nouvelle ! Votre candidature pour le poste de {application.job_offer.title} a été présélectionnée.",
                    related_application=application
                )
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)

    @extend_schema(
        summary="Uploader / préparer le contrat (PDF) pour une candidature",
        request=None,
        responses={200: JobApplicationSerializer},
    )
    @action(detail=True, methods=['post'], url_path='contract/prepare', parser_classes=[MultiPartParser])
    def contract_prepare(self, request, pk=None):
        application = self.get_object()

        contract_file = request.FILES.get('contract_file')
        if not contract_file:
            return Response(
                {'error': 'contract_file est requis (multipart/form-data).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        application.contract_file = contract_file
        application.contract_status = JobApplication.ContractStatus.NOT_PREPARED
        application.save(update_fields=['contract_file', 'contract_status', 'updated_at'])

        serializer = self.get_serializer(application)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Envoyer le contrat par email au candidat (lien public tokenisé)",
        request=None,
        responses={200: OpenApiResponse(description="Contrat envoyé")},
    )
    @action(detail=True, methods=['post'], url_path='contract/send')
    def contract_send(self, request, pk=None):
        application = self.get_object()

        if not application.applicant_email:
            return Response(
                {'error': "Cette candidature n'a pas applicant_email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not application.contract_file:
            return Response(
                {'error': "Aucun contrat n'est attaché à cette candidature. Uploadez d'abord contract_file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(days=7)

        application.contract_token = token
        application.contract_token_expires_at = expires_at
        application.contract_sent_at = timezone.now()
        application.contract_status = JobApplication.ContractStatus.SENT
        application.save(
            update_fields=[
                'contract_token',
                'contract_token_expires_at',
                'contract_sent_at',
                'contract_status',
                'updated_at',
            ]
        )

        frontend_base = os.getenv('FRONTEND_CONTRACT_URL', '').strip().rstrip('/')
        if frontend_base:
            contract_url = f"{frontend_base}/{token}"
        else:
            contract_url = request.build_absolute_uri(f"/api/jobs/contract/{token}/")

        org_name = getattr(getattr(request.user, 'organization', None), 'name', None) or "Notre équipe RH"
        job_title = application.job_offer.title
        candidate_name = application.applicant_name or ""
        deadline_str = expires_at.strftime('%d/%m/%Y à %H:%M')

        subject = f"Signature du contrat – {org_name} – {job_title}"

        text_message = (
            f"Bonjour {candidate_name},\n\n"
            f"Félicitations ! Suite à votre candidature, nous avons le plaisir de vous transmettre votre contrat pour le poste « {job_title} ».\n\n"
            f"Merci de le consulter et de le signer en suivant ce lien :\n"
            f"{contract_url}\n\n"
            f"Date limite de signature : {deadline_str}.\n\n"
            f"Si vous rencontrez la moindre difficulté (accès au lien, téléchargement, dépôt du document signé), répondez simplement à cet email et nous vous assisterons.\n\n"
            f"Cordialement,\n"
            f"{org_name}\n"
        )

        html_message = (
            f"<div style=\"font-family:Arial,Helvetica,sans-serif;line-height:1.5;color:#111\">"
            f"<p>Bonjour <strong>{candidate_name}</strong>,</p>"
            f"<p>Félicitations ! Suite à votre candidature, nous avons le plaisir de vous transmettre votre contrat pour le poste <strong>« {job_title} »</strong>.</p>"
            f"<p style=\"margin:20px 0\">"
            f"<a href=\"{contract_url}\" style=\"display:inline-block;padding:12px 18px;background:#0ea5e9;color:#fff;text-decoration:none;border-radius:8px\">Consulter et signer le contrat</a>"
            f"</p>"
            f"<p><strong>Date limite de signature :</strong> {deadline_str}.</p>"
            f"<p>En cas de difficulté (accès au lien, téléchargement, dépôt du document signé), répondez simplement à cet email et nous vous assisterons.</p>"
            f"<p>Cordialement,<br/>{org_name}</p>"
            f"</div>"
        )

        try:
            send_mail(
                subject,
                text_message,
                None,
                [application.applicant_email],
                html_message=html_message,
            )
        except Exception as e:
            return Response(
                {'error': 'Échec envoi email', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        org = getattr(request.user, 'organization', None)
        if org:
            try:
                Notification.objects.create(
                    organization=org,
                    type=Notification.Types.CONTRACT_SENT,
                    title="Contrat envoyé",
                    message=(
                        f"Le contrat pour « {application.job_offer.title} » a été envoyé à "
                        f"{application.applicant_name} ({application.applicant_email})."
                    ),
                    related_application=application,
                )
            except Exception:
                pass

        if application.user_id:
            try:
                UserNotification.objects.create(
                    user=application.user,
                    type=UserNotification.Types.CONTRACT_SENT,
                    title="Contrat envoyé",
                    message=(
                        f"Votre contrat pour « {application.job_offer.title} » vous a été envoyé par email. "
                        f"Merci de le signer avant le {deadline_str}."
                    ),
                    related_application=application,
                )
            except Exception:
                pass

        return Response(
            {
                'status': 'sent',
                'token': token,
                'expiresAt': expires_at.isoformat(),
                'contractUrl': contract_url,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Assigner les 3 évaluations obligatoires (technique/psychotechnique/personnalité) à une candidature",
        request=None,
        responses={200: JobApplicationSerializer},
    )
    @action(detail=True, methods=['post'], url_path='assign-evaluations')
    def assign_evaluations(self, request, pk=None):
        application = self.get_object()
        job_offer = application.job_offer

        evaluations = [
            getattr(job_offer, 'technical_evaluation', None),
            getattr(job_offer, 'psychotech_evaluation', None),
            getattr(job_offer, 'personality_evaluation', None),
        ]

        if any(e is None for e in evaluations):
            return Response(
                {
                    'error': 'Les 3 évaluations ne sont pas configurées sur cette offre (technical/psychotech/personality).',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not application.applicant_email or not application.applicant_name:
            return Response(
                {
                    'error': 'Cette candidature ne contient pas applicant_email/applicant_name.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone as dj_timezone
        from datetime import timedelta

        expires_at = dj_timezone.now() + timedelta(days=7)

        candidate, _ = Candidate.objects.get_or_create(
            email=application.applicant_email,
            defaults={
                'full_name': application.applicant_name,
                'owner': request.user,
            },
        )

        participant, _ = Participant.objects.get_or_create(
            candidate=candidate,
            defaults={'type': Participant.Type.CANDIDATE},
        )

        created_or_updated = []

        for evaluation in evaluations:
            invitation, _ = EvaluationInvitation.objects.update_or_create(
                evaluation=evaluation,
                candidate=candidate,
                defaults={
                    'expires_at': expires_at,
                },
            )

            SubmissionAttempt.objects.get_or_create(
                participant=participant,
                evaluation=evaluation,
            )

            jae, _ = JobApplicationEvaluation.objects.update_or_create(
                job_application=application,
                evaluation=evaluation,
                defaults={
                    'invitation': invitation,
                    'status': JobApplicationEvaluation.Status.ASSIGNED,
                },
            )

            created_or_updated.append(jae.id)

            try:
                send_invitation_email(request, invitation)
            except Exception:
                pass

        serializer = self.get_serializer(application)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Assigner une évaluation à une candidature",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'evaluation_id': {'type': 'integer'},
                }
            }
        },
        responses={200: JobApplicationSerializer}
    )
    @action(detail=True, methods=['patch'], url_path='assign-evaluation')
    def assign_evaluation(self, request, pk=None):
        """
        Assigne une évaluation à une candidature.
        """
        application = self.get_object()
        evaluation_id = request.data.get('evaluation_id')
        
        if not evaluation_id:
            return Response(
                {'error': 'evaluation_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.evaluations.models import Evaluation
            evaluation = Evaluation.objects.get(id=evaluation_id)
        except Evaluation.DoesNotExist:
            return Response(
                {'error': 'Évaluation non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        application.assigned_evaluation = evaluation
        application.save(update_fields=['assigned_evaluation', 'updated_at'])

        # Créer ou récupérer un candidat externe à partir de la candidature
        # Le candidat n'est pas forcément un utilisateur inscrit dans le système
        if application.applicant_email and application.applicant_name:
            candidate, _ = Candidate.objects.get_or_create(
                email=application.applicant_email,
                defaults={
                    'full_name': application.applicant_name,
                    'owner': request.user,
                },
            )

            # Créer une invitation d'évaluation liée à ce candidat
            # Expiration par défaut : 7 jours à partir de maintenant
            from django.utils import timezone as dj_timezone
            from datetime import timedelta

            expires_at = dj_timezone.now() + timedelta(days=7)

            invitation, _ = EvaluationInvitation.objects.get_or_create(
                evaluation=evaluation,
                candidate=candidate,
                defaults={
                    'expires_at': expires_at,
                },
            )

            # Envoyer l'email d'invitation avec lien direct vers l'évaluation
            # Le contenu de l'email inclut déjà : nom du candidat, organisation, nom du test et lien
            try:
                send_invitation_email(request, invitation)
            except Exception:
                # En cas d'échec d'envoi de mail, on ne doit pas bloquer l'API
                pass

        # Créer une notification interne pour le candidat si c'est un utilisateur
        if application.user:
            from apps.organizations.models import UserNotification
            UserNotification.objects.create(
                user=application.user,
                type='evaluation_assigned',
                title=f"Évaluation assignée pour {application.job_offer.title}",
                message=f"Une évaluation '{evaluation.title}' vous a été assignée pour votre candidature au poste de {application.job_offer.title}.",
                related_application=application,
                related_evaluation=evaluation
            )

        serializer = self.get_serializer(application)
        return Response(serializer.data)

    @extend_schema(
        summary="Résultats d'évaluation pour une candidature",
        description=(
            "Retourne, pour une candidature donnée, les informations sur l'évaluation assignée "
            "et la dernière tentative du candidat (score, statut, etc.)."
        ),
        responses={200: JobApplicationSerializer}
    )
    @action(detail=True, methods=['get'], url_path='evaluation-results')
    def evaluation_results(self, request, pk=None):
        """Retourne les résultats d'évaluation d'une candidature (vue agrégée)."""
        application = self.get_object()

        job_offer = application.job_offer
        evaluations = [
            getattr(job_offer, 'technical_evaluation', None),
            getattr(job_offer, 'psychotech_evaluation', None),
            getattr(job_offer, 'personality_evaluation', None),
        ]

        evaluations = [e for e in evaluations if e is not None]
        if not evaluations:
            return Response({
                "applicationId": application.id,
                "jobOfferId": application.job_offer_id,
                "candidate": {
                    "name": application.applicant_name,
                    "email": application.applicant_email,
                },
                "evaluations": [],
                "globalScore": None,
            })

        from django.db.models import Q

        type_labels = {
            'technical': "Évaluation technique",
            'logical': "Évaluation logique",
            'personality': "Évaluation de personnalité",
            'psychotech': "Évaluation psychotechnique",
            'competition': "Compétition",
        }

        evaluation_payloads = []
        percent_scores = []

        for evaluation in evaluations:
            attempts_qs = SubmissionAttempt.objects.filter(evaluation=evaluation).select_related('submission', 'evaluation')
            candidate_filter = Q()
            if application.applicant_email:
                candidate_filter |= Q(participant__candidate__email=application.applicant_email)
            if application.user_id:
                candidate_filter |= Q(participant__user=application.user)
            attempts_qs = attempts_qs.filter(candidate_filter)

            latest_attempt = attempts_qs.order_by('-started_at').first()

            status_value = 'assigned'
            score = None
            max_score = evaluation.max_score
            avg_on_20 = None
            completed_at = None

            if latest_attempt:
                if latest_attempt.is_completed and latest_attempt.submission:
                    status_value = 'completed'
                    score = latest_attempt.submission.score
                    completed_at = latest_attempt.ended_at
                else:
                    status_value = 'started'

                if score is not None and max_score:
                    try:
                        avg_on_20 = float(score) * 20.0 / float(max_score)
                    except Exception:
                        avg_on_20 = None

            if score is not None and max_score:
                try:
                    percent_scores.append(float(score) * 100.0 / float(max_score))
                except Exception:
                    pass

            type_code = getattr(evaluation, 'evaluation_type', '') or ''
            type_label = type_labels.get(type_code, type_code or "Évaluation")

            evaluation_payloads.append({
                "evaluationId": evaluation.id,
                "attemptId": latest_attempt.id if latest_attempt else None,
                "type": type_code,
                "typeLabel": type_label,
                "title": evaluation.title,
                "status": status_value,
                "score": float(score) if score is not None else None,
                "maxScore": float(max_score) if max_score is not None else None,
                "averageOn20": avg_on_20,
                "completedAt": completed_at.isoformat() if completed_at else None,
            })

        global_score = None
        if len(percent_scores) == 3:
            try:
                global_score = sum(percent_scores) / 3.0
            except Exception:
                global_score = None

        payload = {
            "applicationId": application.id,
            "jobOfferId": application.job_offer_id,
            "candidate": {
                "name": application.applicant_name,
                "email": application.applicant_email,
            },
            "evaluations": evaluation_payloads,
            "globalScore": global_score,
        }

        return Response(payload, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Planifier un entretien pour une candidature",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'interview_date': {'type': 'string', 'format': 'date-time'},
                    'interview_duration': {'type': 'integer'},
                    'interview_link': {'type': 'string'},
                    'interview_type': {'type': 'string'},
                    'interview_notes': {'type': 'string'},
                }
            }
        },
        responses={200: JobApplicationSerializer}
    )
    @action(detail=True, methods=['patch'], url_path='schedule-interview')
    def schedule_interview(self, request, pk=None):
        """
        Planifie un entretien pour une candidature.
        """
        application = self.get_object()
        
        application.interview_date = request.data.get('interview_date')
        application.interview_duration = request.data.get('interview_duration', 40)
        application.interview_link = request.data.get('interview_link', '')
        application.interview_type = request.data.get('interview_type', 'individuel')
        application.interview_notes = request.data.get('interview_notes', '')
        
        application.save(update_fields=[
            'interview_date', 'interview_duration', 'interview_link', 
            'interview_type', 'interview_notes', 'updated_at'
        ])
        
        # Créer une notification pour le candidat
        if application.user and application.interview_date:
            from apps.organizations.models import UserNotification
            from datetime import datetime
            interview_date_str = datetime.fromisoformat(str(application.interview_date).replace('Z', '+00:00')).strftime('%d/%m/%Y à %H:%M')
            UserNotification.objects.create(
                user=application.user,
                type='interview_scheduled',
                title=f"Entretien programmé pour {application.job_offer.title}",
                message=f"Votre entretien pour le poste de {application.job_offer.title} est programmé le {interview_date_str}. Lien: {application.interview_link}",
                related_application=application
            )
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)

    @extend_schema(
        summary="Récupérer tous les candidats recrutés de l'organisation",
        responses={200: JobApplicationSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='recruited')
    def recruited(self, request):
        """
        Récupère tous les candidats avec le statut 'accepted' (recrutés) pour l'organisation connectée.
        """
        recruited_applications = self.get_queryset().filter(status='accepted').order_by('-updated_at')
        serializer = self.get_serializer(recruited_applications, many=True)
        return Response({'results': serializer.data})


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


@extend_schema(tags=["Contrats"], exclude=False)
class PublicContractView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Récupérer les informations du contrat via un token public",
        responses={200: OpenApiResponse(description="Contrat trouvé"), 404: OpenApiResponse(description="Token invalide")},
    )
    def get(self, request, token: str):
        application = JobApplication.objects.filter(contract_token=token).select_related('job_offer').first()
        if not application:
            return Response({'detail': 'Token invalide'}, status=status.HTTP_404_NOT_FOUND)

        expires_at = application.contract_token_expires_at
        if expires_at and timezone.now() > expires_at:
            return Response({'detail': 'Token expiré'}, status=status.HTTP_410_GONE)

        contract_url = None
        try:
            contract_url = application.contract_file.url if application.contract_file else None
        except Exception:
            contract_url = None

        return Response(
            {
                'applicationId': application.id,
                'jobOfferId': application.job_offer_id,
                'jobTitle': application.job_offer.title,
                'candidate': {
                    'name': application.applicant_name,
                    'email': application.applicant_email,
                },
                'contractStatus': application.contract_status,
                'expiresAt': expires_at.isoformat() if expires_at else None,
                'contractFileUrl': contract_url,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Contrats"], exclude=False)
class PublicContractUploadSignedView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="Uploader le contrat signé (PDF) via token public",
        request=None,
        responses={200: OpenApiResponse(description="Contrat signé reçu")},
    )
    def post(self, request, token: str):
        application = JobApplication.objects.filter(contract_token=token).select_related('job_offer').first()
        if not application:
            return Response({'detail': 'Token invalide'}, status=status.HTTP_404_NOT_FOUND)

        expires_at = application.contract_token_expires_at
        if expires_at and timezone.now() > expires_at:
            return Response({'detail': 'Token expiré'}, status=status.HTTP_410_GONE)

        signed_file = request.FILES.get('signed_contract_file')
        if not signed_file:
            return Response(
                {'detail': 'signed_contract_file est requis (multipart/form-data).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        application.signed_contract_file = signed_file
        application.contract_status = JobApplication.ContractStatus.SIGNED
        application.contract_signed_at = timezone.now()
        application.save(
            update_fields=['signed_contract_file', 'contract_status', 'contract_signed_at', 'updated_at']
        )

        org = getattr(application.job_offer, 'company', None)
        if org:
            try:
                Notification.objects.create(
                    organization=org,
                    type=Notification.Types.CONTRACT_SIGNED,
                    title="Contrat signé reçu",
                    message=(
                        f"{application.applicant_name} ({application.applicant_email}) a déposé le contrat signé "
                        f"pour « {application.job_offer.title} »."
                    ),
                    related_application=application,
                )
            except Exception:
                pass

        if application.user_id:
            try:
                UserNotification.objects.create(
                    user=application.user,
                    type=UserNotification.Types.CONTRACT_SIGNED,
                    title="Contrat signé envoyé",
                    message=(
                        f"Votre contrat signé pour « {application.job_offer.title} » a bien été reçu par l'équipe RH."
                    ),
                    related_application=application,
                )
            except Exception:
                pass

        return Response(
            {
                'status': 'signed',
                'applicationId': application.id,
                'signedAt': application.contract_signed_at.isoformat() if application.contract_signed_at else None,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=['Métadonnées'])
class JobMetadataView(APIView):
    """
    Retourne les métadonnées pour les offres d'emploi (types, statuts, documents requis, etc.)
    Cette API permet au frontend d'afficher les listes déroulantes sans dupliquer les choix.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        from apps.evaluations.models import ExperienceLevel
        
        # Utilisation de camelCase pour être cohérent avec le reste de l'API DRF
        return Response({
            'jobTypes': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in JobOffer.JobType.choices
            ],
            'experienceLevels': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in ExperienceLevel.choices
            ],
            'requiredDocumentTypes': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in JobOffer.RequiredDocumentType.choices
            ],
            'statusChoices': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in JobOffer.Status.choices
            ],
        })
