from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiRequest
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.serializers import ListSerializer

from evaluations.corrector import correct_submission
from evaluations.models import Evaluation, SubmissionAttempt, Submission
from evaluations.permissions import RejectUnConstructedEvaluation
from evaluations.serializers import EvaluationSerializer, AnswerSerializer, SubmissionAttemptSerializer
from questions.models import Question


class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.prefetch_related(
        'questions', 'questions__choices').select_related('technology').all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def verify_attempt(self, request, session_pk: int, ended=False):
        attempt = get_object_or_404(SubmissionAttempt, pk=session_pk)
        if attempt.is_finished and not ended:
            raise ValidationError('This attempt is finished')
        return attempt

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]

        if self.action in map(lambda f: f.__name__, self.get_extra_actions()):
            permissions = super().get_permissions()
            if not settings.DEBUG:
                permissions.append(RejectUnConstructedEvaluation())
            return permissions
        # TODO only candidate, admin

        return super().get_permissions()

    @action(detail=False, methods=['get'], url_path='slug/(?P<slug>[^/.]+)')
    def get_by_slug(self, request, slug: str):
        evaluation = get_object_or_404(self.get_queryset(), slug=slug)
        serializer = self.get_serializer(evaluation)
        return Response(serializer.data)

    @extend_schema(
        request=OpenApiRequest(),
        responses={
            200: SubmissionAttemptSerializer
        }
    )
    @action(detail=True, methods=['post'], url_path='start-session')
    def start_session(self, request, pk: int):
        attempt = SubmissionAttempt.objects.create(
            evaluation=self.get_object(),
            candidate=request.user,
        )
        questions = self.get_object().questions.filter(
            status=Question.Status.PUBLISHED,
        ).exclude(is_translated__isnull=True).order_by('?')[:20]
        attempt.questions.add(*questions)
        attempt.save()
        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ListSerializer(child=AnswerSerializer()),
    )
    @action(detail=True, methods=['post'], url_path=r'sessions/(?P<session_pk>\d+)')
    @transaction.atomic
    def submit_session(self, request, pk: int, session_pk: int):
        """
        Submit answers to a session
        """
        attempt = self.verify_attempt(request, session_pk)
        for answer_data in request.data:
            answer = AnswerSerializer(data=answer_data)
            answer.is_valid(raise_exception=True)
            answer.save(attempt=attempt)
        attempt.save()
        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data)

    @extend_schema(
        request=OpenApiRequest(),
        responses={
            200: SubmissionAttemptSerializer
        }
    )
    @action(detail=True, methods=['post'], url_path=r'sessions/(?P<session_pk>\d+)/finalize')
    @transaction.atomic
    def finalize_session(self, request, pk: int, session_pk: int):
        attempt = self.verify_attempt(request, session_pk)
        submission = Submission.objects.create()
        submission.attempt = attempt
        correct_submission(submission)
        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data)

    @extend_schema(
        request=OpenApiRequest(),
        responses={
            200: SubmissionAttemptSerializer
        }
    )
    @action(detail=True, methods=['get'], url_path=r'sessions/(?P<session_pk>\d+)/results')
    def session_results(self, request, pk: int, session_pk: int):
        attempt = self.verify_attempt(request, session_pk, ended=True)
        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data)

    @extend_schema(
        request=OpenApiRequest(),
        responses={
            200: ListSerializer(child=SubmissionAttemptSerializer())
        }
    )
    @action(detail=True, methods=['get'], url_path=r'attempts')
    def get_attempts(self, request, pk: int):
        queryset = SubmissionAttempt.objects.filter(evaluation=self.get_object()).order_by('-started_at')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SubmissionAttemptSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = SubmissionAttemptSerializer(queryset, many=True)
        return Response(serializer.data)
