from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from questions.filters import QuestionFilterSet
from questions.models import Question
from questions.serializers import QuestionSerializer


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.prefetch_related('choices').all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['text', 'technology__name', 'technology__professions__title']
    filterset_class = QuestionFilterSet

    # TODO question is added to a specific test

    # def get_permissions(self):
    #     return []
    #     if self.request.method not in SAFE_METHODS:
    #         return [IsAuthenticatedOrReadOnly(), IsQuestionNotPending()]
    #     return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)
