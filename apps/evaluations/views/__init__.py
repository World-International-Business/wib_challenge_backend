from django.db import transaction, models
from django.db.models import Avg, Q, F, Min, Max, Count, Sum, Case, When, FloatField
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiRequest, extend_schema_view
from rest_access_policy import AccessViewSetMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.serializers import ListSerializer

from apps.evaluations.filters import (
    EvaluationFilterSet
)
from apps.evaluations.models import (
    Evaluation, EvaluationType, SubmissionAttempt, Submission, Answer
)
from apps.evaluations.policy import EvaluationPolicy
from apps.evaluations.serializers import (
    EvaluationSerializer, InviteCandidateSerializer,
    EvaluationInvitationSerializer, SubmissionAttemptListSerializer
)
from apps.evaluations.serializers.results import CandidateResultSerializer, SubmissionAttemptDetailSerializer
from apps.evaluations.serializers.stats import (
    UserEvaluationStatisticsSerializer,
    DetailedEvaluationStatisticsSerializer
)
from apps.questions.models import Question
from wib_challenge.pagination import paginated_response


@extend_schema_view(
    list=extend_schema(
        summary="Liste des évaluations",
        description="Récupère la liste des évaluations disponibles avec filtres et recherche",
    ),
    create=extend_schema(
        summary="Créer une évaluation",
        description="Crée une nouvelle évaluation (admin uniquement)",
    ),
    retrieve=extend_schema(
        summary="Détails d'une évaluation",
        description="Récupère les détails d'une évaluation spécifique",
    ),
    update=extend_schema(
        summary="Mettre à jour une évaluation",
        description="Met à jour une évaluation (admin uniquement)",
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'une évaluation",
        description="Met à jour partiellement une évaluation (admin uniquement)",
    ),
    destroy=extend_schema(
        summary="Supprimer une évaluation",
        description="Supprime une évaluation (admin uniquement)",
    )
)
@extend_schema(tags=['Évaluations'])
class EvaluationViewSet(AccessViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet pour gérer les évaluations et les sessions d'évaluation
    """
    serializer_class = EvaluationSerializer
    access_policy = EvaluationPolicy

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EvaluationFilterSet
    search_fields = ['title', 'description', 'technology__name', 'profession__title']
    ordering_fields = ['created_at', 'updated_at', 'title', 'difficulty']
    ordering = ['-created_at']

    def get_queryset(self):
        """Retourne le queryset optimisé, avec filtres et annotations cohérentes"""
        queryset = (
            Evaluation.objects
            .select_related('technology', 'profession', 'publisher', 'competition')
            .prefetch_related(
                Prefetch(
                    'questions',
                    queryset=Question.objects.filter(status=Question.Status.PUBLISHED)
                )
            )
            .annotate(
                questions_count=models.Count(
                    'questions',
                    filter=Q(questions__status=Question.Status.PUBLISHED),
                    distinct=True
                )
            )
        )

        if self.action == 'list':
            queryset = queryset.exclude(evaluation_type=EvaluationType.COMPETITION)

        user = self.request.user
        if user.is_authenticated:
            if not user.is_staff:
                queryset = queryset.filter(
                    ((
                             Q(archived=True, publisher=user) |
                             Q(archived=False)
                     ) & (
                             Q(questions_count__gte=20) |
                             Q(publisher=user)
                     )) | (Q(attempts__participant__user=user) if 'result' in self.action else Q())
                )
        else:
            queryset = queryset.filter(archived=False, questions_count__gte=20)

        return queryset

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)

    @method_decorator(cache_page(60 * 5))
    @extend_schema(
        summary="Évaluation par slug",
        description="Récupère une évaluation par son identifiant slug",
    )
    @action(detail=False, methods=['get'], url_path='slug/(?P<slug>[^/.]+)')
    def get_by_slug(self, request, slug: str):
        """Récupère une évaluation par son slug"""
        evaluation = get_object_or_404(self.get_queryset(), slug=slug)
        serializer = self.get_serializer(evaluation)
        return Response(serializer.data)

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

    @extend_schema(
        request=InviteCandidateSerializer
    )
    @action(detail=True, methods=['post'], url_path='invite-candidates')
    @transaction.atomic
    def invite_candidates(self, request, pk=None, organization_pk=None):
        """Crée une invitation pour un candidat"""
        evaluation = self.get_object()
        candidates = request.data.get('candidates', [])
        expires_at = request.data.get('expires_at')

        for candidate in candidates:
            serializer = EvaluationInvitationSerializer(
                data={**candidate, 'expires_at': expires_at}, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save(evaluation=evaluation)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: ListSerializer(child=SubmissionAttemptListSerializer())},
        summary="Mes tentatives d'évaluation",
        description="Récupère toutes mes tentatives pour une évaluation",
    )
    @action(detail=True, methods=['get'], url_path='my-attempts')
    def my_attempts(self, request, pk: int):
        """Récupère toutes les tentatives pour une évaluation"""
        evaluation = self.get_object()
        attempts = evaluation.attempts.select_related(
            'participant__user', 'participant__candidate', 'submission'
        ).prefetch_related('answers')

        attempts = attempts.filter(participant__user=request.user)

        return paginated_response(self, attempts, SubmissionAttemptListSerializer)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: ListSerializer(child=SubmissionAttemptListSerializer())},
        summary="Mes tentatives d'évaluation",
        description="Récupère toutes mes tentatives pour une évaluation",
    )
    @action(detail=False, methods=['get'], url_path='my-attempts')
    def all_my_attempts(self, request, pk: int):
        """Récupère toutes les tentatives pour une évaluation"""
        attempts = SubmissionAttempt.objects.select_related(
            'participant__user', 'participant__candidate', 'submission'
        ).prefetch_related('answers')

        return paginated_response(self, attempts, SubmissionAttemptListSerializer)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: ListSerializer(child=SubmissionAttemptListSerializer())},
        summary="Tentatives d'évaluation",
        description="Récupère toutes les tentatives pour une évaluation",
    )
    @action(detail=True, methods=['get'], url_path=r'attempts')
    def get_attempts(self, request, pk: int):
        """Récupère toutes les tentatives pour une évaluation"""
        evaluation = self.get_object()
        attempts = evaluation.attempts.select_related(
            'participant__user', 'participant__candidate', 'submission'
        ).prefetch_related('answers')

        if not request.user.is_staff:
            attempts = attempts.filter(Q(evaluation__publisher=request.user) | Q(participant__user=request.user))

        return paginated_response(self, attempts, SubmissionAttemptListSerializer)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: ListSerializer(child=CandidateResultSerializer())},
        summary="Résultats d'une évaluation",
        description="Récupère les résultats d'une évaluation",
    )
    @action(detail=True, url_path='results')
    def results(self, request, pk=None):
        """Récupère les résultats d'une évaluation"""
        evaluation: Evaluation = self.get_object()
        attempts = evaluation.attempts.filter(
            Q(evaluation__publisher=request.user) | Q(participant__user=request.user),
            is_completed=True,
        )
        return paginated_response(self, attempts, CandidateResultSerializer)

    @extend_schema(
        request=OpenApiRequest(),
        responses={200: SubmissionAttemptDetailSerializer},
        summary="Résultat d'une évaluation",
        description="Récupère un résultat d'une évaluation",
    )
    @action(detail=True, url_path=r'results/(?P<result_id>[^/.]+)')
    def result(self, request, pk=None, result_id=None):
        """Récupère les résultats d'une évaluation"""
        evaluation: Evaluation = self.get_object()
        attempt = evaluation.attempts.filter(
            Q(evaluation__publisher=request.user) | Q(participant__user=request.user),
            is_completed=True,
            id=result_id
        ).first()
        if not attempt:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(SubmissionAttemptDetailSerializer(attempt).data)

    @extend_schema(
        summary="Statistiques globales",
        description="Récupère les statistiques globales des évaluations de l'utilisateur connecté",
        tags=["Statistiques"],
        responses={
            200: UserEvaluationStatisticsSerializer,
            401: {"description": "Non authentifié"},
            403: {"description": "Accès interdit"}
        }
    )
    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """
        Retourne les statistiques globales des évaluations de l'utilisateur connecté
        """
        if not request.user.is_authenticated:
            return Response({
                'error': 'Authentification requise'
            }, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user

        global_stats = self.get_queryset().filter(publisher=user).aggregate(
            total_evaluations=Count('id'),
            active_evaluations=Count('id', filter=Q(archived=False)),
            total_attempts=Count('attempts', distinct=True),
            total_completed=Count('attempts', filter=Q(attempts__is_completed=True), distinct=True),
            total_participants=Count('attempts__participant', distinct=True),
            average_score=Avg('attempts__submission__score'),
            total_questions=Sum('questions_count')
        )

        top_participants = SubmissionAttempt.objects.filter(
            evaluation__publisher=user
        ).values(
            'participant__user__first_name',
            'participant__user__last_name',
            'participant__candidate__full_name'
        ).annotate(
            total_attempts=Count('id'),
            completed_attempts=Count('id', filter=Q(is_completed=True)),
            best_score=Max('submission__score'),
            average_score=Avg('submission__score'),
            evaluations_participated=Count('evaluation', distinct=True)
        ).order_by('-best_score', '-average_score')[:10]

        formatted_top_participants = []
        for participant in top_participants:
            first_name = participant['participant__user__first_name'] or ""
            last_name = participant['participant__user__last_name'] or ""
            candidate_name = participant['participant__candidate__full_name'] or ""

            name = f"{first_name} {last_name}".strip() if first_name or last_name else candidate_name

            formatted_top_participants.append({
                'participant_name': name or "Participant anonyme",
                'total_attempts': participant['total_attempts'],
                'completed_attempts': participant['completed_attempts'],
                'best_score': participant['best_score'] or 0,
                'average_score': round(participant['average_score'] or 0, 2),
                'evaluations_participated': participant['evaluations_participated']
            })

        total_attempts = global_stats['total_attempts'] or 0
        total_completed = global_stats['total_completed'] or 0
        completion_rate = round((total_completed / total_attempts * 100), 2) if total_attempts > 0 else 0

        response_data = {
            'total_evaluations_created': global_stats['total_evaluations'] or 0,
            'active_evaluations': global_stats['active_evaluations'] or 0,
            'total_attempts_received': total_attempts,
            'total_completed_attempts': total_completed,
            'average_completion_rate': completion_rate,
            'total_participants': global_stats['total_participants'] or 0,
            'average_score': round(global_stats['average_score'] or 0, 2),
            'total_questions': global_stats['total_questions'] or 0,
            'top_participants': formatted_top_participants,
            'last_updated': timezone.now()
        }

        serializer = UserEvaluationStatisticsSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Statistiques détaillées d'une évaluation",
        description="Récupère les statistiques détaillées d'une évaluation spécifique",
        tags=["Statistiques"],
        responses={
            200: DetailedEvaluationStatisticsSerializer,
            401: {"description": "Non authentifié"},
            403: {"description": "Accès interdit - Vous n'êtes pas le propriétaire de cette évaluation"},
            404: {"description": "Évaluation non trouvée"}
        }
    )
    @action(detail=True, methods=['get'], url_path='statistics')
    def evaluation_statistics(self, request, pk=None):
        """
        Retourne les statistiques détaillées d'une évaluation spécifique
        """
        if not request.user.is_authenticated:
            return Response({
                'error': 'Authentification requise'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            evaluation = self.get_object()
        except Evaluation.DoesNotExist:
            return Response({
                'error': 'Évaluation non trouvée'
            }, status=status.HTTP_404_NOT_FOUND)

        if evaluation.publisher != request.user and not request.user.is_staff:
            return Response({
                'error': 'Vous n\'avez pas l\'autorisation de voir ces statistiques'
            }, status=status.HTTP_403_FORBIDDEN)

        base_stats = SubmissionAttempt.objects.filter(evaluation=evaluation).aggregate(
            total_attempts=Count('id'),
            completed_attempts=Count('id', filter=Q(is_completed=True)),
            total_participants=Count('participant', distinct=True),
            average_score=Avg('submission__score'),
            min_score=Min('submission__score'),
            max_score=Max('submission__score'),
            avg_time=Avg(
                F('ended_at') - F('started_at'),
                filter=Q(ended_at__isnull=False, started_at__isnull=False, is_completed=True)
            )
        )

        max_possible = evaluation.max_score
        if max_possible > 0:
            score_distribution = Submission.objects.filter(
                attempt__evaluation=evaluation
            ).aggregate(
                excellent=Count('id', filter=Q(score__gte=max_possible * 0.8)),
                good=Count('id', filter=Q(score__gte=max_possible * 0.6, score__lt=max_possible * 0.8)),
                average=Count('id', filter=Q(score__gte=max_possible * 0.4, score__lt=max_possible * 0.6)),
                poor=Count('id', filter=Q(score__lt=max_possible * 0.4))
            )
        else:
            score_distribution = {'excellent': 0, 'good': 0, 'average': 0, 'poor': 0}

        questions_stats = []
        question_answers = Answer.objects.filter(
            attempt__evaluation=evaluation
        ).values('question__id', 'question__title').annotate(
            total_answers=Count('id'),
            correct_answers=Count('id', filter=Q(is_correct=True))
        ).annotate(
            success_rate=Case(
                When(total_answers=0, then=0.0),
                default=F('correct_answers') * 100.0 / F('total_answers'),
                output_field=FloatField()
            )
        )

        for q_stat in question_answers:
            question_title = q_stat['question__title'] or ""
            questions_stats.append({
                'question_id': q_stat['question__id'],
                'question_title': (question_title[:100] + '...') if len(question_title) > 100 else question_title,
                'total_answers': q_stat['total_answers'],
                'correct_answers': q_stat['correct_answers'],
                'success_rate': round(q_stat['success_rate'], 2)
            })

        top_participants = SubmissionAttempt.objects.filter(
            evaluation=evaluation
        ).values(
            'participant__user__first_name',
            'participant__user__last_name',
            'participant__candidate__full_name'
        ).annotate(
            attempts_count=Count('id'),
            completed_count=Count('id', filter=Q(is_completed=True)),
            best_score=Max('submission__score')
        ).order_by('-best_score')[:10]

        formatted_participants = []
        for participant in top_participants:
            first_name = participant['participant__user__first_name'] or ""
            last_name = participant['participant__user__last_name'] or ""
            candidate_name = participant['participant__candidate__full_name'] or ""

            name = f"{first_name} {last_name}".strip() if first_name or last_name else candidate_name

            formatted_participants.append({
                'participant_name': name or "Participant anonyme",
                'attempts_count': participant['attempts_count'],
                'completed': participant['completed_count'],
                'best_score': participant['best_score'] or 0
            })

        avg_time_seconds = base_stats['avg_time'].total_seconds() if base_stats['avg_time'] else 0
        avg_time_minutes = round(avg_time_seconds / 60, 2)

        completion_rate = (
            round((base_stats['completed_attempts'] / base_stats['total_attempts'] * 100), 2)
            if base_stats['total_attempts'] > 0 else 0
        )

        stats = {
            'evaluation_id': evaluation.id,
            'evaluation_title': evaluation.title,
            'evaluation_description': evaluation.description or "",
            'total_attempts': base_stats['total_attempts'] or 0,
            'completed_attempts': base_stats['completed_attempts'] or 0,
            'average_score': round(base_stats['average_score'] or 0, 2),
            'max_score_possible': evaluation.max_score,
            'min_score': base_stats['min_score'] or 0,
            'max_score': base_stats['max_score'] or 0,
            'completion_rate': completion_rate,
            'total_participants': base_stats['total_participants'] or 0,
            'questions_count': evaluation.questions.count(),
            'average_time_minutes': avg_time_minutes,
            'score_distribution': score_distribution,
            'questions_statistics': questions_stats,
            'top_participants': formatted_participants,
            'created_at': evaluation.created_at,
            'archived': evaluation.archived,
            'last_updated': timezone.now()
        }

        return Response(stats, status=status.HTTP_200_OK)
