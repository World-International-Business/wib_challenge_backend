from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from evaluations.models import Evaluation
from evaluations.serializers import EvaluationSerializer


class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.prefetch_related('questions', 'technologies', 'questions__choices').all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['get'], url_path='slug/(?P<slug>[^/.]+)')
    def get_by_slug(self, request, slug: str):
        evaluation = get_object_or_404(self.get_queryset(), slug=slug)
        serializer = self.get_serializer(evaluation)
        return self.response(serializer.data)
