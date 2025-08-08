from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiRequest, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.serializers import ListSerializer

from apps.evaluations.filters import (
    EvaluationFilterSet, SubmissionAttemptFilterSet, CandidateFilterSet
)
from apps.evaluations.models import (
    Evaluation, SubmissionAttempt, EvaluationType, Candidate
)
from apps.evaluations.permissions import RejectUnConstructedEvaluation
from apps.evaluations.serializers import (
    EvaluationSerializer, AnswerSerializer, SubmissionAttemptSerializer,
    SubmissionSerializer, CandidateSerializer
)
from apps.questions.models import Question
from services.corrector import correct_submission


@extend_schema_view(
    list=extend_schema(
        summary="Liste des évaluations",
        description="Récupère la liste des évaluations disponibles avec filtres et recherche",
        tags=["Évaluations"]
    ),
    create=extend_schema(
        summary="Créer une évaluation",
        description="Crée une nouvelle évaluation (admin uniquement)",
        tags=["Évaluations"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une évaluation",
        description="Récupère les détails d'une évaluation spécifique",
        tags=["Évaluations"]
    ),
    update=extend_schema(
        summary="Mettre à jour une évaluation",
        description="Met à jour une évaluation (admin uniquement)",
        tags=["Évaluations"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'une évaluation",
        description="Met à jour partiellement une évaluation (admin uniquement)",
        tags=["Évaluations"]
    ),
    destroy=extend_schema(
        summary="Supprimer une évaluation",
        description="Supprime une évaluation (admin uniquement)",
        tags=["Évaluations"]
    )
)
class EvaluationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les évaluations et les sessions d'évaluation
    """
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EvaluationFilterSet
    search_fields = ['title', 'description', 'technology__name', 'profession__title']
    ordering_fields = ['created_at', 'updated_at', 'title', 'difficulty']
    ordering = ['-created_at']

    def get_queryset(self):
        """Retourne le queryset avec les jointures optimisées, excluant les compétitions"""
        queryset = Evaluation.objects.prefetch_related('questions', 'questions__choices').select_related('technology',
                                                                                                         'profession')
        if self.action == 'list':
            queryset = queryset.exclude(evaluation_type=EvaluationType.COMPETITION)
        return queryset

    @staticmethod
    def verify_attempt(request, session_pk: int, ended=False):
        """Vérifie si la tentative existe et appartient à l'utilisateur actuel"""
        attempt = get_object_or_404(SubmissionAttempt.objects.select_related('submission'), pk=session_pk)

        user_ct = ContentType.objects.get_for_model(request.user.__class__)
        if not request.user.is_staff and not (
                attempt.candidate_content_type == user_ct and
                attempt.candidate_object_id == request.user.id
        ):
            raise PermissionDenied(_("Vous n'avez pas accès à cette tentative"))

        if attempt.is_finished and not ended:
            raise ValidationError(_('Cette tentative est déjà terminée'))
        return attempt

    @staticmethod
    def verify_competition_active(evaluation):
        """Vérifie si une compétition est active"""
        if evaluation.evaluation_type == EvaluationType.COMPETITION:
            try:
                competition = evaluation.competition
                now = timezone.now()

                if competition.started_at and competition.started_at > now:
                    raise ValidationError(_('Cette compétition n\'a pas encore commencé'))

                if competition.ended_at and competition.ended_at < now:
                    raise ValidationError(_('Cette compétition est terminée'))

            except Evaluation.competition.RelatedObjectDoesNotExist:
                raise ValidationError(_('Configuration de compétition manquante'))

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]

        if self.action in [fn.__name__ for fn in self.get_extra_actions()]:
            permissions = super().get_permissions()
            if not settings.DEBUG:
                permissions.append(RejectUnConstructedEvaluation())
            return permissions

        return super().get_permissions()

    @method_decorator(cache_page(60 * 5))
    @extend_schema(
        summary="Évaluation par slug",
        description="Récupère une évaluation par son identifiant slug",
        tags=["Évaluations"]
    )
    @action(detail=False, methods=['get'], url_path='slug/(?P<slug>[^/.]+)')
    def get_by_slug(self, request, slug: str):
        """Récupère une évaluation par son slug"""
        evaluation = get_object_or_404(self.get_queryset(), slug=slug)
        serializer = self.get_serializer(evaluation)
        return Response(serializer.data)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: SubmissionAttemptSerializer},
        summary="Démarrer une session",
        description="Démarre une nouvelle session d'évaluation pour l'utilisateur connecté",
        tags=["Sessions d'évaluation"]
    )
    @action(detail=True, methods=['post'], url_path='start-session')
    def start_session(self, request, pk: int):
        """Démarre une nouvelle session d'évaluation"""
        evaluation = self.get_object()

        user_ct = ContentType.objects.get_for_model(request.user.__class__)
        attempt = SubmissionAttempt.objects.create(
            evaluation=evaluation,
            candidate_content_type=user_ct,
            candidate_object_id=request.user.id
        )

        questions = evaluation.questions.filter(status=Question.Status.PUBLISHED)
        if evaluation.questions_order == evaluation.QuestionOrder.RANDOM:
            questions = questions.order_by('?')
        elif evaluation.questions_order == evaluation.QuestionOrder.SKILL:
            questions = questions.order_by('difficulty')

        min_questions = 5 if hasattr(evaluation.publisher, 'organization') else 20
        questions = questions[:min_questions]

        attempt.questions.set(questions)

        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ListSerializer(child=AnswerSerializer()),
        summary="Soumettre des réponses",
        description="Soumet les réponses aux questions d'une session",
        tags=["Sessions d'évaluation"]
    )
    @action(detail=True, methods=['post'], url_path=r'sessions/(?P<session_pk>\d+)')
    @transaction.atomic
    def submit_session(self, request, pk: int, session_pk: int):
        """
        Soumet des réponses pour une session
        """
        attempt = self.verify_attempt(request, session_pk)

        answers_data = request.data if isinstance(request.data, list) else [request.data]
        created_answers = []

        for answer_data in answers_data:
            answer_data['attempt'] = attempt.id
            serializer = AnswerSerializer(data=answer_data)
            serializer.is_valid(raise_exception=True)
            created_answers.append(serializer.save())

        serializer = AnswerSerializer(created_answers, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: SubmissionAttemptSerializer},
        summary="Finaliser une session",
        description="Finalise une session d'évaluation et calcule le score final",
        tags=["Sessions d'évaluation"]
    )
    @action(detail=True, methods=['post'], url_path=r'sessions/(?P<session_pk>\d+)/finalize')
    @transaction.atomic
    def finalize_session(self, request, pk: int, session_pk: int):
        """Finalise une session et calcule le score"""
        attempt = self.verify_attempt(request, session_pk)

        if attempt.submission:
            raise ValidationError(_('Cette session a déjà été finalisée'))

        correct_submission(attempt)
        attempt.ended_at = timezone.now()
        attempt.is_completed = True
        attempt.corrected = True
        attempt.save()

        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @method_decorator(cache_page(60 * 30))
    @extend_schema(
        request=OpenApiRequest(),
        responses={200: SubmissionSerializer},
        summary="Résultats d'une session",
        description="Récupère les résultats détaillés d'une session terminée",
        tags=["Sessions d'évaluation"]
    )
    @action(detail=True, methods=['get'], url_path=r'sessions/(?P<session_pk>\d+)/results')
    def session_results(self, request, pk: int, session_pk: int):
        """Récupère les résultats d'une session"""
        attempt = self.verify_attempt(request, session_pk, ended=True)

        if not attempt.submission:
            raise ValidationError(_('Cette session n\'a pas encore été finalisée'))

        serializer = SubmissionSerializer(attempt.submission)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: ListSerializer(child=SubmissionAttemptSerializer())},
        summary="Tentatives d'évaluation",
        description="Récupère toutes les tentatives pour une évaluation",
        tags=["Sessions d'évaluation"]
    )
    @action(detail=True, methods=['get'], url_path=r'attempts')
    def get_attempts(self, request, pk: int):
        """Récupère toutes les tentatives pour une évaluation"""
        evaluation = self.get_object()
        attempts = evaluation.attempts.all()

        if not request.user.is_staff:
            user_ct = ContentType.objects.get_for_model(request.user.__class__)
            attempts = attempts.filter(
                candidate_content_type=user_ct,
                candidate_object_id=request.user.id
            )

        serializer = SubmissionAttemptSerializer(attempts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: ListSerializer(child=EvaluationSerializer())},
        summary="Liste des compétitions",
        description="Récupère toutes les compétitions disponibles",
        tags=["Compétitions"]
    )
    @action(detail=False, methods=['get'], url_path='competitions')
    def competitions(self, request):
        """Récupère toutes les compétitions"""
        competitions = self.get_queryset().filter(evaluation_type=EvaluationType.COMPETITION)
        serializer = self.get_serializer(competitions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: ListSerializer(child=EvaluationSerializer())},
        summary="Compétitions actives",
        description="Récupère les compétitions actuellement actives",
        tags=["Compétitions"]
    )
    @action(detail=False, methods=['get'], url_path='competitions/active')
    def active_competitions(self, request):
        """Récupère les compétitions actives"""
        now = timezone.now()
        active_competitions = self.get_queryset().filter(
            evaluation_type=EvaluationType.COMPETITION,
            competition__started_at__lte=now,
            competition__ended_at__gte=now
        )
        serializer = self.get_serializer(active_competitions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des candidats externes",
        description="Récupère la liste des candidats externes avec filtres",
        tags=["Candidats externes"]
    ),
    create=extend_schema(
        summary="Créer un candidat externe",
        description="Crée un nouveau candidat externe",
        tags=["Candidats externes"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un candidat externe",
        description="Récupère les détails d'un candidat externe",
        tags=["Candidats externes"]
    ),
    update=extend_schema(
        summary="Mettre à jour un candidat externe",
        description="Met à jour un candidat externe",
        tags=["Candidats externes"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'un candidat externe",
        description="Met à jour partiellement un candidat externe",
        tags=["Candidats externes"]
    ),
    destroy=extend_schema(
        summary="Supprimer un candidat externe",
        description="Supprime un candidat externe",
        tags=["Candidats externes"]
    )
)
class CandidateViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les candidats externes
    """
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CandidateFilterSet
    search_fields = ['full_name', 'email']
    ordering_fields = ['created_at', 'updated_at', 'full_name', 'email']
    ordering = ['-created_at']

    def get_queryset(self):
        """Retourne uniquement les candidats de l'utilisateur connecté"""
        if self.request.user.is_staff:
            return Candidate.objects.select_related('owner').all()
        return Candidate.objects.filter(owner=self.request.user).select_related('owner')

    def perform_create(self, serializer):
        """Assigne automatiquement le propriétaire lors de la création"""
        serializer.save(owner=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des tentatives",
        description="Récupère la liste des tentatives d'évaluation avec filtres",
        tags=["Tentatives d'évaluation"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une tentative",
        description="Récupère les détails d'une tentative d'évaluation",
        tags=["Tentatives d'évaluation"]
    )
)
class SubmissionAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet en lecture seule pour les tentatives de soumission
    """
    serializer_class = SubmissionAttemptSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SubmissionAttemptFilterSet
    search_fields = ['evaluation__title']
    ordering_fields = ['started_at', 'ended_at', 'is_completed']
    ordering = ['-started_at']

    def get_queryset(self):
        """Retourne les tentatives selon les permissions"""
        queryset = SubmissionAttempt.objects.select_related(
            'evaluation', 'submission'
        ).prefetch_related('questions', 'answers')

        if self.request.user.is_staff:
            return queryset

        user_ct = ContentType.objects.get_for_model(self.request.user.__class__)
        return queryset.filter(
            candidate_content_type=user_ct,
            candidate_object_id=self.request.user.id
        )
