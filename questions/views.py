from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly, SAFE_METHODS

from questions.filters import QuestionFilterSet
from questions.models import Question
from questions.permissions import IsQuestionNotPending
from questions.serializers import QuestionSerializer


class QuestionViewSetMixin:
    queryset = Question.objects.prefetch_related('choices').all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['text', 'technology__name', 'technology__professions__title']
    filterset_class = QuestionFilterSet

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_staff:
            return queryset
        elif self.request.user.is_authenticated:
            return queryset.filter(
                Q(status=Question.Status.REJECTED, publisher=self.request.user) | ~Q(status=Question.Status.REJECTED)
            )
        else:
            return queryset.exclude(status=Question.Status.REJECTED)


class ReadOnlyQuestionViewSet(QuestionViewSetMixin, viewsets.ReadOnlyModelViewSet):
    pass


class QuestionViewSet(QuestionViewSetMixin, viewsets.ModelViewSet):

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(evaluation=self.kwargs['evaluation_pk'])

    def get_permissions(self):
        if self.request.method not in SAFE_METHODS:
            return [permission() for permission in [*self.permission_classes, IsQuestionNotPending]]
        return super().get_permissions()
