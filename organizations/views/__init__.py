from django.shortcuts import get_object_or_404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated

from organizations.models import (Organization, OrgEvaluation, OrgQuestion)
from organizations.permissions import IsOrganization
from organizations.serializers import (OrganizationSerializer, OrgQuestionSerializer)
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
        OpenApiParameter('evaluation_id', type=int, description='ID de l\'évaluation')
    ]
)
class OrgQuestionViewSet(mixins.DestroyModelMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = OrgQuestionSerializer
    permission_classes = [IsAuthenticated, IsOrganization | ReadOnly]

    def get_queryset(self):
        if hasattr(self.request.user, 'organization'):
            evaluation_id = self.request.GET.get('evaluation_id')
            queryset = OrgQuestion.objects.filter(evaluation__organization=self.request.user.organization)
            if evaluation_id:
                queryset = queryset.filter(evaluation_id=evaluation_id)
            return queryset
        return OrgQuestion.objects.none()

    def perform_create(self, serializer):
        evaluation_id = self.request.GET.get('evaluation_id')
        evaluation = get_object_or_404(OrgEvaluation, id=evaluation_id, organization=self.request.user.organization)
        serializer.save(evaluation=evaluation)
