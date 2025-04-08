from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from evaluations.corrector import correct_submission
from evaluations.models import Evaluation, SubmissionAttempt, Submission
from evaluations.serializers import EvaluationSerializer, AnswerSerializer, SubmissionAttemptSerializer
from wib_challenge.permissions import ReadOnly


class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.prefetch_related('questions', 'technologies', 'questions__choices').all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsAdminUser | ReadOnly]

    @action(detail=False, methods=['get'], url_path='slug/(?P<slug>[^/.]+)')
    def get_by_slug(self, request, slug: str):
        evaluation = get_object_or_404(self.get_queryset(), slug=slug)
        serializer = self.get_serializer(evaluation)
        return Response(serializer.data)

    @extend_schema(
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
        questions = self.get_object().questions.order_by('?').limit(20)
        attempt.questions.add(*questions)
        attempt.save()
        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data)

    @extend_schema(
        request=AnswerSerializer,
    )
    @action(detail=True, methods=['post'], url_path='session/(?P<pk>\d+)/')
    def submit_session(self, request, pk: int):
        """
        Submit answers to a session
        """
        attempt = get_object_or_404(SubmissionAttempt, pk=pk)
        answer = AnswerSerializer(data=request.data)
        answer.is_valid(raise_exception=True)
        answer.save(attempt=attempt)
        attempt.save()
        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data)

    @extend_schema(
        responses={
            200: SubmissionAttemptSerializer
        }
    )
    @action(detail=True, methods=['post'], url_path='session/(?P<pk>\d+)/finalize')
    @transaction.atomic
    def get_session(self, request, pk: int):
        attempt = get_object_or_404(SubmissionAttempt, pk=pk)
        submission = Submission.objects.create(
            attempt=attempt,
            candidate=attempt.candidate,
            evaluation=attempt.evaluation
        )
        correct_submission(submission, attempt, save=False)
        submission.save()
