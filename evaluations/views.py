from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from evaluations.models import Evaluation
from evaluations.serializers import EvaluationSerializer


class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.prefetch_related('questions', 'technologies', 'questions__choices').all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
