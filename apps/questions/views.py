from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.core.models import Technology
from apps.evaluations.models import EvaluationType
from apps.questions.filters import QuestionFilterSet
from apps.questions.models import Question
from apps.questions.permissions import IsQuestionOwner
from apps.questions.serializers import QuestionSerializer, TechnologyStats
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
                                                                                               'technology__professions').exclude(
            evaluations__evaluation_type=EvaluationType.PERSONALITY
        )
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
    ),
    retrieve=extend_schema(
        summary="Détails d'une question",
        description="Récupère les détails d'une question spécifique avec ses choix de réponses",
    )
)
@extend_schema(tags=['Questions'])
class ReadOnlyQuestionViewSet(QuestionViewSetMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=None,
        responses={200: TechnologyStats},
    )
    @action(detail=False, methods=['get'], url_path='technology-stats/<int:tech_pk>', url_name='technology-stats')
    def technology_stats(self, request, tech_pk=None, organization_pk=None):
        """
        Retrieve statistics for a specific technology in the organization.
        """
        technology = get_object_or_404(Technology.objects.prefetch_related('questions'), pk=tech_pk)

        questions = technology.questions.all()
        nb_questions = questions.count()

        available = {
            Question.Difficulty.EASY: questions.filter(difficulty=Question.Difficulty.EASY).count(),
            Question.Difficulty.MEDIUM: questions.filter(difficulty=Question.Difficulty.MEDIUM).count(),
            Question.Difficulty.HARD: questions.filter(difficulty=Question.Difficulty.HARD).count()
        }

        return Response({
            'id': technology.id,
            'name': technology.name,
            'url': request.build_absolute_uri(technology.image.url) if technology.image else None,
            'question_count': nb_questions,
            'available': available,
        }, status=200)
