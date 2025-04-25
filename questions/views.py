from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticatedOrReadOnly, SAFE_METHODS

from evaluations.models import Evaluation
from questions.filters import QuestionFilterSet
from questions.models import Question
from questions.permissions import IsQuestionNotPending
from questions.serializers import QuestionSerializer


class QuestionViewSetMixin:
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['text', 'technology__name', 'choices__text']
    filterset_class = QuestionFilterSet

    def get_queryset(self):
        queryset = (Question.objects
                    .select_related('publisher', 'technology', 'evaluation')
                    .prefetch_related('choices', 'technology__professions')
                    )

        user = self.request.user
        if user.is_staff:
            return queryset
        elif user.is_authenticated:
            return queryset.filter(
                Q(status=Question.Status.REJECTED, publisher=user) | ~Q(status=Question.Status.REJECTED))
        else:
            return queryset.exclude(status=Question.Status.REJECTED)


class ReadOnlyQuestionViewSet(QuestionViewSetMixin, viewsets.ReadOnlyModelViewSet):
    @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class QuestionViewSet(QuestionViewSetMixin, viewsets.ModelViewSet):
    _evaluation = None  #

    def get_evaluation(self):
        if self._evaluation is None:
            self._evaluation = get_object_or_404(Evaluation, pk=self.kwargs['evaluation_pk'])
        return self._evaluation

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(evaluation_id=self.kwargs['evaluation_pk'])

    def get_permissions(self):
        if self.request.method not in SAFE_METHODS:
            return [permission() for permission in self.permission_classes + [IsQuestionNotPending]]
        return super().get_permissions()

    def perform_create(self, serializer):
        evaluation = self.get_evaluation()
        kwargs = {'evaluation': evaluation, 'publisher': self.request.user, 'technology': evaluation.technology}
        if self.request.user.is_staff:
            kwargs['status'] = Question.Status.PUBLISHED
        serializer.save(**kwargs)
