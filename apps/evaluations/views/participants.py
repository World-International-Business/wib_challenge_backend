from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework_nested.viewsets import NestedViewSetMixin

from apps.evaluations.models import Participant
from apps.evaluations.serializers import ParticipantSerializer


@extend_schema(
    tags=['Evaluation Participants'],
    parameters=[
        OpenApiParameter(name='evaluation_pk', type=int, location=OpenApiParameter.PATH)
    ]
)
class ParticipantViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Participant.objects.all()
    serializer_class = ParticipantSerializer
    permission_classes = [IsAuthenticated]
    parent_lookup_kwargs = {
        'evaluation_pk': 'attempts__evaluation__pk',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(
            attempts__evaluation__publisher=self.request.user
        )
