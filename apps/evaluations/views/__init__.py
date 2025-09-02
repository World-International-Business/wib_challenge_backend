from django.contrib.auth import get_user_model
from django.db import transaction, models
from django.db.models import Avg, Q, F, Min, Max, Count, Sum, Case, When, FloatField, QuerySet
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_access_policy import AccessViewSetMixin
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.serializers import ListSerializer

from apps.evaluations.filters import (
    EvaluationFilterSet
)
from apps.evaluations.models import (
    Evaluation, EvaluationType, SubmissionAttempt, Submission, Answer, ExperienceLevel, SkillEvaluation
)
from apps.evaluations.policy import EvaluationPolicy
from apps.evaluations.serializers import (
    EvaluationSerializer, InviteCandidateSerializer,
    EvaluationInvitationSerializer, SubmissionAttemptListSerializer, SkillEvaluationSerializer
)
from apps.evaluations.serializers.evaluations import ProportionEvaluationSerializer, EvaluationResponseSerializer
from apps.evaluations.serializers.results import CandidateResultSerializer, SubmissionAttemptDetailSerializer
from apps.evaluations.serializers.stats import (
    UserEvaluationStatisticsSerializer,
    DetailedEvaluationStatisticsSerializer
)
from apps.evaluations.utils import send_reminder_email
from apps.evaluations.views.generated import create_evaluation_from_techs
from apps.questions.models import Question
from apps.questions.serializers import AddQuestionSerializer, QuestionSerializer
from wib_challenge.pagination import paginated_response


@extend_schema(tags=['Évaluations'])
class EvaluationSearchView(AccessViewSetMixin, generics.ListAPIView, generics.CreateAPIView, viewsets.GenericViewSet):
    serializer_class = EvaluationSerializer
    queryset = Evaluation.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EvaluationFilterSet
    search_fields = ['title', 'description', 'technology__name', 'profession__title']
    ordering_fields = ['created_at', 'updated_at', 'title', 'difficulty']
    ordering = ['-created_at']
    access_policy = EvaluationPolicy

    def get_queryset(self):
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

        user = self.request.user
        if user.is_authenticated:
            if not user.is_staff:
                queryset = queryset.filter(
                    (
                            Q(archived=True, publisher=user) |
                            Q(archived=False)
                    ) & (
                            Q(questions_count__gte=20) |
                            Q(publisher=user)
                    )
                )
        else:
            queryset = queryset.filter(archived=False, questions_count__gte=20)

        return queryset.exclude(
            Q(skill_evaluations__isnull=False) & Q(skill_evaluations__user=user) if user.is_authenticated else Q())

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)


@extend_schema_view(
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
class EvaluationViewSet(AccessViewSetMixin, generics.RetrieveUpdateDestroyAPIView,
                        viewsets.GenericViewSet):
    """
    ViewSet pour gérer les évaluations et les sessions d'évaluation
    """
    serializer_class = EvaluationSerializer
    access_policy = EvaluationPolicy
    lookup_value_converter = 'int'

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

        return queryset

    @method_decorator(cache_page(60 * 5))
    @extend_schema(
        summary="Évaluation par slug",
        description="Récupère une évaluation par son identifiant slug",
    )
    @action(detail=False, methods=['get'], url_path='slug/<slug:slug>')
    def get_by_slug(self, request, slug: str):
        """Récupère une évaluation par son slug"""
        evaluation = get_object_or_404(self.get_queryset(), slug=slug)
        serializer = self.get_serializer(evaluation)
        return Response(serializer.data)

    @extend_schema(
        request=None,
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
        request=None,
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
        request=None,
        responses={200: EvaluationResponseSerializer}
    )
    @action(detail=True, methods=['get'], url_path='grouped')
    def grouped(self, request, pk=None):
        return Response(EvaluationResponseSerializer(self.get_object(), context={'request': request}).data)

    @extend_schema(
        request=InviteCandidateSerializer,
        responses=None
    )
    @action(detail=True, methods=['post'], url_path='candidates/invite')
    @transaction.atomic
    def invite_candidates(self, request, pk=None):
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
        request=None,
        parameters=[
            OpenApiParameter(name='invite_id', type=int, location=OpenApiParameter.PATH)
        ],
        responses=None
    )
    @action(detail=True, methods=['post'], url_path='candidates/<str:invite_id>/remind')
    @transaction.atomic
    def remind_candidate(self, request, pk=None, invite_id=None):
        """ Envoie un rappel à un candidat """
        evaluation = self.get_object()
        invitation = evaluation.invitations.filter(id=invite_id, evaluation=evaluation,
                                                   expires_at__gte=timezone.now()).first()
        if not invitation:
            return Response(status=status.HTTP_404_NOT_FOUND)

        send_reminder_email(request, invitation)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=None,
        responses={200: ListSerializer(child=SubmissionAttemptListSerializer())},
        summary="Mes tentatives d'évaluation",
        description="Récupère toutes mes tentatives pour une évaluation",
    )
    @action(detail=True, methods=['get'], url_path='my-attempts')
    def my_attempts(self, request, pk: int):
        """Récupère toutes les tentatives pour une évaluation"""
        try:
            evaluation = self.get_object()
            attempts = evaluation.attempts.select_related(
                'participant__user', 'participant__candidate', 'submission'
            ).prefetch_related('answers')

            attempts = attempts.filter(participant__user=request.user)

            return paginated_response(self, attempts, SubmissionAttemptListSerializer)
        except Evaluation.DoesNotExist:
            return Response(_("Evaluation not found"), status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        request=None,
        responses={200: ListSerializer(child=SubmissionAttemptListSerializer())},
        summary="Mes tentatives d'évaluation",
        description="Récupère toutes mes tentatives pour une évaluation",
    )
    @action(detail=False, methods=['get'], url_path='my-attempts')
    def all_my_attempts(self, request):
        """Récupère toutes les tentatives pour une évaluation"""
        attempts = SubmissionAttempt.objects.select_related(
            'participant__user', 'participant__candidate', 'submission'
        ).prefetch_related('answers').filter(participant__user=request.user)

        return paginated_response(self, attempts, SubmissionAttemptListSerializer)

    @extend_schema(
        request=None,
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
        request=None,
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
            # is_completed=True,
        )
        return paginated_response(self, attempts, CandidateResultSerializer)

    @extend_schema(
        request=None,
        parameters=[
            OpenApiParameter(name='result_id', type=int, location=OpenApiParameter.PATH)
        ],
        responses={200: SubmissionAttemptDetailSerializer},
        summary="Résultat d'une évaluation",
        description="Récupère un résultat d'une évaluation",
    )
    @action(detail=True, url_path=r'results/<int:result_id>')
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

    def check_can_update(self, evaluation: Evaluation):
        if Evaluation.objects.filter(
                id=evaluation.id, attempts__started_at__isnull=False,
        ).exists():
            raise ValidationError(
                _("Cette évaluation ne peut pas être modifiée."))

    @extend_schema(
        request=ProportionEvaluationSerializer,
        responses={200: EvaluationResponseSerializer},
        summary="Mise à jour par proportions personnalisées",
        description="Ajoute ou remplace des questions selon des proportions personnalisées par technologie et difficulté",
    )
    @transaction.atomic
    @action(detail=True, methods=['put', 'post'], url_path='add-question-basic', url_name='add-question-basic')
    def update_by_proportion(self, request, pk=None):
        """
        Mise à jour d'une évaluation avec des proportions personnalisées
        Format attendu :
        {
            "proportions" : [
                {
                    "technology": 1,
                    "easy": 3,
                    "medium": 8,
                    "hard": 7
                },
                {...}
            ],
            "replace_existing" : true/false
        }
        """
        evaluation = self.get_object()
        self.check_can_update(evaluation)
        if evaluation.evaluation_type == EvaluationType.PERSONALITY:
            raise ValidationError(
                _("Cette évaluation ne peut pas avoir de questions technologiques/techniques."))

        serializer = ProportionEvaluationSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        proportions = serializer.validated_data['proportions']
        replace_existing = serializer.validated_data['replace_existing']

        if replace_existing:
            evaluation.questions.all().delete()
        else:
            evaluation.questions.filter(technology__isnull=False).delete()

        for prop in proportions:
            technology = prop['technology']
            num_easy = prop.get('easy', 0)
            num_medium = prop.get('medium', 0)
            num_hard = prop.get('hard', 0)

            if num_easy > 0:
                easy_questions = Question.objects.filter(
                    technology=technology,
                    difficulty=Question.Difficulty.EASY,
                    status=Question.Status.PUBLISHED
                ).order_by('?')[:num_easy]

                self._add_questions_to_evaluation(evaluation, easy_questions)

            if num_medium > 0:
                medium_questions = Question.objects.filter(
                    technology=technology,
                    difficulty=Question.Difficulty.MEDIUM,
                    status=Question.Status.PUBLISHED
                ).order_by('?')[:num_medium]

                self._add_questions_to_evaluation(evaluation, medium_questions)

            if num_hard > 0:
                hard_questions = Question.objects.filter(
                    technology=technology,
                    difficulty=Question.Difficulty.HARD,
                    status=Question.Status.PUBLISHED
                ).order_by('?')[:num_hard]

                self._add_questions_to_evaluation(evaluation, hard_questions)

        evaluation.refresh_from_db()
        response_data = EvaluationResponseSerializer(evaluation, context={'request': request}).data
        return Response(response_data)

    @extend_schema(
        request=AddQuestionSerializer,
        responses={200: EvaluationResponseSerializer},
        summary="Ajout manuel de questions",
        description="Ajoute une question soit en utilisant une question existante, soit en créant une nouvelle",
    )
    @action(detail=True, methods=['put', 'post'], url_path='add-question', url_name='add-question')
    def add_question(self, request, pk=None):
        """
        Ajout manuel de questions à une évaluation:
        - Soit en créant de nouvelles questions
        - Soit en ajoutant des questions existantes
        """
        evaluation = self.get_object()
        self.check_can_update(evaluation)
        serializer = AddQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        evaluation.questions.add(serializer.validated_data['question'])
        serializer_data = EvaluationResponseSerializer(evaluation, context={'request': request}).data
        return Response(serializer_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=QuestionSerializer,
        responses={200: EvaluationResponseSerializer},
        summary="Ajout manuel de questions",
        description="Ajoute une question soit en utilisant une question existante, soit en créant une nouvelle",
    )
    @action(detail=True, methods=['put', 'post'], url_path='add-question/scratch', url_name='add-question-scratch')
    def add_from_scratch(self, request, pk=None):
        """
        Ajout manuel de questions à une évaluation:
        - Soit en créant de nouvelles questions
        - Soit en ajoutant des questions existantes
        """
        evaluation = self.get_object()
        self.check_can_update(evaluation)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        evaluation.questions.add(instance)
        serializer_data = EvaluationResponseSerializer(evaluation, context={'request': request}).data
        return Response(serializer_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None
    )
    @action(detail=False, methods=['post'], url_path='test-skills')
    def test_skills(self, request):
        techs = request.user.profile.technologies.all()
        if not techs.exists():
            raise ValidationError(_('Vous devez avoir au moins une technologie pour tester vos compétences'))
        evaluation = create_evaluation_from_techs(
            publisher=get_user_model().objects.filter(is_superuser=True).first(),
            title=f"Évaluation Des Compétences de base",
            description=f"Évaluation automatique pour les compétences de base",
            experience_level=ExperienceLevel.INTERMEDIATE,
            technologies=techs
        )
        SkillEvaluation.objects.create(evaluation=evaluation, user=request.user)
        return Response(EvaluationSerializer(evaluation).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses={200: ListSerializer(child=SkillEvaluationSerializer())}
    )
    @test_skills.mapping.get
    def get_test_skills(self, request):
        evaluations = request.user.profile.skill_evaluations.all()
        return paginated_response(self, evaluations, SkillEvaluationSerializer)

    @staticmethod
    def _add_questions_to_evaluation(evaluation: Evaluation, questions: QuerySet[Question, Question]):
        """Helper pour ajouter des questions à l'évaluation"""
        question_ids = list(questions.values_list('id', flat=True))

        evaluation.questions.add(*question_ids)
