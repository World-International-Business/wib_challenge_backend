from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, OpenApiRequest
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.serializers import ListSerializer

from corrector import correct_submission
from evaluations.models import Evaluation, SubmissionAttempt, Submission, Answer, EvaluationType
from evaluations.permissions import RejectUnConstructedEvaluation
from evaluations.serializers import EvaluationSerializer, AnswerSerializer, SubmissionAttemptSerializer, \
    SubmissionSerializer
from questions.models import Question


class EvaluationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les évaluations et les sessions d'évaluation
    """
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """Retourne le queryset avec les jointures optimisées, excluant les compétitions"""
        queryset = Evaluation.objects.prefetch_related('questions', 'questions__choices').select_related('technology',
                                                                                                         'profession')
        if self.action == 'list':
            queryset = queryset.filter(evaluation_type=EvaluationType.NORMAL)
        return queryset

    @staticmethod
    def verify_attempt(request, session_pk: int, ended=False):
        """Vérifie si la tentative existe et appartient à l'utilisateur actuel"""
        attempt = get_object_or_404(SubmissionAttempt.objects.select_related('submission'), pk=session_pk)

        if not request.user.is_staff and attempt.candidate != request.user:
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
    @action(detail=False, methods=['get'], url_path='slug/(?P<slug>[^/.]+)')
    def get_by_slug(self, request, slug: str):
        """Récupère une évaluation par son slug"""
        evaluation = get_object_or_404(self.get_queryset(), slug=slug)
        serializer = self.get_serializer(evaluation)
        return Response(serializer.data)

    @extend_schema(request=OpenApiRequest(), responses={200: SubmissionAttemptSerializer})
    @action(detail=True, methods=['post'], url_path='start-session')
    def start_session(self, request, pk: int):
        """Démarre une nouvelle session d'évaluation"""
        evaluation = self.get_object()

        self.verify_competition_active(evaluation)

        existing_attempt = SubmissionAttempt.objects.filter(evaluation=evaluation, candidate=request.user,
                                                            submission__isnull=True).first()

        if existing_attempt:
            serializer = SubmissionAttemptSerializer(existing_attempt)
            return Response(serializer.data, status=status.HTTP_200_OK)

        with transaction.atomic():
            attempt = SubmissionAttempt.objects.create(evaluation=evaluation, candidate=request.user, )

            questions = evaluation.questions.filter(status=Question.Status.PUBLISHED).order_by('?')[:20]

            if questions.count() < 20:
                raise ValidationError(_("Cette évaluation n'a pas assez de questions publiées"))

            attempt.questions.set(questions)

        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ListSerializer(child=AnswerSerializer()), )
    @action(detail=True, methods=['post'], url_path=r'sessions/(?P<session_pk>\d+)')
    @transaction.atomic
    def submit_session(self, request, pk: int, session_pk: int):
        """
        Soumet des réponses pour une session
        """
        attempt = self.verify_attempt(request, session_pk)

        self.verify_competition_active(attempt.evaluation)

        answers_to_create = []

        excluded_question_ids = attempt.answers.values_list('question_id', flat=True)

        for answer_data in request.data:
            try:
                serializer = AnswerSerializer(data=answer_data)
                serializer.is_valid(raise_exception=True)
                if serializer.validated_data['question'].id in excluded_question_ids:
                    continue
                answer = Answer(attempt=attempt, question_id=serializer.validated_data['question'].id,
                                delta_time=serializer.validated_data.get('delta_time', 0),
                                status=serializer.validated_data.get('status', Answer.Status.PENDING))
                answers_to_create.append(answer)
            except (ValidationError, IntegrityError) as e:
                raise ValidationError(_('Données de réponse invalides: {}').format(e))

        if answers_to_create:
            Answer.objects.bulk_create(answers_to_create)
            for i, answer in enumerate(answers_to_create):
                answer_obj = Answer.objects.get(attempt=attempt, question_id=answer.question_id)
                selected_choices = request.data[i].get('selected_choices', [])
                answer_obj.selected_choices.set(selected_choices)

        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data)

    @extend_schema(request=OpenApiRequest(), responses={200: SubmissionAttemptSerializer})
    @action(detail=True, methods=['post'], url_path=r'sessions/(?P<session_pk>\d+)/finalize')
    @transaction.atomic
    def finalize_session(self, request, pk: int, session_pk: int):
        """Finalise une session et calcule le score"""
        attempt = self.verify_attempt(request, session_pk)

        self.verify_competition_active(attempt.evaluation)

        questions_count = attempt.questions.count()
        answers_count = attempt.answers.count()

        if answers_count < questions_count:
            raise ValidationError(
                _('Toutes les questions n\'ont pas été répondues ({}/{})').format(answers_count, questions_count))

        submission = Submission.objects.create()
        attempt.submission = submission
        attempt.save()

        correct_submission(submission, attempt)
        attempt.refresh_from_db()
        serializer = SubmissionAttemptSerializer(attempt, context={'request': request})
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 30))
    @extend_schema(request=OpenApiRequest(), responses={200: SubmissionSerializer})
    @action(detail=True, methods=['get'], url_path=r'sessions/(?P<session_pk>\d+)/results')
    def session_results(self, request, pk: int, session_pk: int):
        """Récupère les résultats d'une session"""
        attempt = self.verify_attempt(request, session_pk, ended=True)

        if not attempt.is_finished:
            raise ValidationError(_('Cette tentative n\'est pas encore terminée'))

        submission = attempt.submission
        if submission is None:
            raise ValidationError(_('Cette tentative n\'a pas de soumission. Avez-vous finalisé la session?'))

        if submission.score is None:
            correct_submission(submission, attempt)
            submission.refresh_from_db()

        serializer = SubmissionSerializer(submission, context={'request': request})
        return Response(serializer.data)

    @extend_schema(request=OpenApiRequest(), responses={200: ListSerializer(child=SubmissionAttemptSerializer())})
    @action(detail=True, methods=['get'], url_path=r'attempts')
    def get_attempts(self, request, pk: int):
        """Récupère toutes les tentatives pour une évaluation"""
        queryset = SubmissionAttempt.objects.filter(evaluation=self.get_object()).select_related('candidate',
                                                                                                 'evaluation',
                                                                                                 'submission').prefetch_related(
            'questions', 'answers').order_by('-started_at')

        if not request.user.is_staff:
            queryset = queryset.filter(candidate=request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SubmissionAttemptSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = SubmissionAttemptSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(request=OpenApiRequest(), responses={200: ListSerializer(child=EvaluationSerializer())})
    @action(detail=False, methods=['get'], url_path='competitions')
    def competitions(self, request):
        """Récupère toutes les compétitions"""
        queryset = Evaluation.objects.filter(evaluation_type=EvaluationType.COMPETITION).prefetch_related(
            'competition', 'questions', 'questions__choices'
        ).select_related('technology', 'profession')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(request=OpenApiRequest(), responses={200: ListSerializer(child=EvaluationSerializer())})
    @action(detail=False, methods=['get'], url_path='competitions/active')
    def active_competitions(self, request):
        """Récupère les compétitions actives"""
        now = timezone.now()
        queryset = Evaluation.objects.filter(
            evaluation_type=EvaluationType.COMPETITION,
            competition__started_at__lte=now,
            competition__ended_at__gte=now
        ).prefetch_related(
            'competition', 'questions', 'questions__choices'
        ).select_related('technology', 'profession')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
