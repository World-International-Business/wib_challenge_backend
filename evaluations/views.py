from django.conf import settings
from django.db import transaction, IntegrityError
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
from evaluations.models import Evaluation, SubmissionAttempt, Submission, Answer
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
        """Retourne le queryset avec les jointures optimisées"""
        return Evaluation.objects.prefetch_related('questions', 'questions__choices').select_related('technology',
                                                                                                     'profession')

    @staticmethod
    def verify_attempt(request, session_pk: int, ended=False):
        """Vérifie si la tentative existe et appartient à l'utilisateur actuel"""
        attempt = get_object_or_404(SubmissionAttempt.objects.select_related('submission'), pk=session_pk)

        # Vérification que l'utilisateur a les droits sur cette tentative
        if not request.user.is_staff and attempt.candidate != request.user:
            raise PermissionDenied(_("Vous n'avez pas accès à cette tentative"))

        if attempt.is_finished and not ended:
            raise ValidationError(_('Cette tentative est déjà terminée'))
        return attempt

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

    @method_decorator(cache_page(60 * 5))  # Cache pendant 5 minutes
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

        existing_attempt = SubmissionAttempt.objects.filter(evaluation=evaluation, candidate=request.user,
                                                            submission__isnull=True).first()

        if existing_attempt:
            serializer = SubmissionAttemptSerializer(existing_attempt)
            # TODO add logic to Submission serializer for excluding questions with answers
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
