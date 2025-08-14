from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework_nested.viewsets import NestedViewSetMixin

from apps.questions.models import Question
from apps.questions.views import QuestionViewSetMixin


@extend_schema(
    tags=["Evaluation Questions"]
)
class EvaluationQuestionsViewSet(QuestionViewSetMixin, NestedViewSetMixin, viewsets.ModelViewSet):
    parent_lookup_kwargs = {
        'evaluation_pk': 'evaluations__pk',
    }

    def perform_create(self, serializer):
        instance = serializer.save(publisher=self.request.user,
                                   status=Question.Status.PUBLISHED if not self.request.user.is_dev else Question.Status.PENDING)
        instance.evaluations.add(int(self.kwargs['evaluation_pk']))

    def perform_update(self, serializer):
        instance = serializer.save(publisher=self.request.user,
                                   status=Question.Status.PUBLISHED if not self.request.user.is_dev else Question.Status.PENDING)
