from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import Technology
from organizations.models import (Organization, OrgEvaluation, OrgQuestion)
from organizations.permissions import IsOrganization
from organizations.serializers import (
    OrganizationSerializer, OrgQuestionSerializer)
from organizations.serializers.evaluations import TechnologyStats
from apps.questions.models import Question
from wib_challenge.permissions import ReadOnly


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'organization'):
            return Organization.objects.filter(id=self.request.user.organization.id)
        elif self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.none()


@extend_schema(
    parameters=[
        OpenApiParameter('evaluation_id', type=int,
                         description='ID de l\'évaluation'),
        OpenApiParameter('organization_id', type=int,
                         description='ID de la technologie', location=OpenApiParameter.PATH)
    ]
)
class OrgQuestionViewSet(mixins.DestroyModelMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = OrgQuestionSerializer
    permission_classes = [IsAuthenticated, IsOrganization | ReadOnly]

    def get_queryset(self):
        if hasattr(self.request.user, 'organization'):
            evaluation_id = self.request.GET.get('evaluation_id')
            queryset = OrgQuestion.objects.filter(
                evaluation__organization=self.request.user.organization)
            if evaluation_id:
                queryset = queryset.filter(evaluation_id=evaluation_id)
            return queryset
        return OrgQuestion.objects.none()

    def perform_create(self, serializer):
        evaluation_id = self.request.GET.get('evaluation_id')
        evaluation = get_object_or_404(
            OrgEvaluation, id=evaluation_id, organization=self.request.user.organization)
        serializer.save(evaluation=evaluation)

    @extend_schema(
        request=None,
        responses={200: TechnologyStats},
    )
    @action(detail=False, methods=['get'], url_path='technology-stats/(?P<tech_pk>[0-9]+)', url_name='technology-stats')
    def technology_stats(self, request, tech_pk=None, organization_pk=None):
        """
        Retrieve statistics for a specific technology in the organization.
        """
        technology = get_object_or_404(Technology, pk=tech_pk)

        questions = technology.questions.all()
        nb_questions = questions.count()

        available = {
            Question.Difficulty.EASY: questions.filter(difficulty=Question.Difficulty.EASY).count(),
            Question.Difficulty.MEDIUM: questions.filter(difficulty=Question.Difficulty.MEDIUM).count(),
            Question.Difficulty.HARD: questions.filter(
                difficulty=Question.Difficulty.HARD).count()
        }

        return Response({
            'id': technology.id,
            'name': technology.name,
            'url': request.build_absolute_uri(technology.image.url) if technology.image else None,
            'question_count': nb_questions,
            'available': available,
        }, status=200)
