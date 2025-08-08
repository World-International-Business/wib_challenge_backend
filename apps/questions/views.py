from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, mixins
from rest_framework.filters import SearchFilter

from apps.questions.filters import QuestionFilterSet
from apps.questions.models import Question
from apps.questions.permissions import IsQuestionOwner
from apps.questions.serializers import QuestionSerializer
from wib_challenge.permissions import ReadOnly


class QuestionViewSetMixin:
    serializer_class = QuestionSerializer
    permission_classes = [IsQuestionOwner | ReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['text', 'technology__name', 'choices__text']
    filterset_class = QuestionFilterSet
    queryset = Question.objects.all()

    def get_queryset(self):
        queryset = Question.objects.select_related('publisher', 'technology').prefetch_related('choices',
                                                                                               'technology__professions')

        user = self.request.user
        if user.is_staff:
            return queryset
        elif user.is_authenticated:
            return queryset.filter(
                Q(status=Question.Status.REJECTED, publisher=user) | ~Q(status=Question.Status.REJECTED))
        else:
            return queryset.exclude(status=Question.Status.REJECTED)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des questions",
        description="Récupère la liste paginée des questions avec filtres et recherche",
        tags=["Questions"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une question",
        description="Récupère les détails d'une question spécifique avec ses choix de réponses",
        tags=["Questions"]
    )
)
class ReadOnlyQuestionViewSet(QuestionViewSetMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
