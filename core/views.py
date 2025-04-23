from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.filters import SearchFilter

from core.models import Profession, Technology
from core.serializers import ProfessionSerializer, TechnologySerializer
from wib_challenge.permissions import ReadOnly


class ProfessionViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionSerializer
    queryset = Profession.objects.prefetch_related('technologies').all()
    permission_classes = [IsAdminUser | ReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['title']


class TechnologyViewSet(viewsets.ModelViewSet):
    serializer_class = TechnologySerializer
    queryset = Technology.objects.order_by('name')
    permission_classes = [IsAdminUser | ReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name']
