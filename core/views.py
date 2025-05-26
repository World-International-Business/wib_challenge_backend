from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAdminUser
from django.http import HttpResponse

from core.filters import TechnologyFilter, ProfessionFilter, DomainFilter
from core.models import Profession, Technology, Domain
from core.serializers import ProfessionSerializer, ProfessionDetailSerializer, TechnologySerializer, DomainSerializer
from wib_challenge.permissions import ReadOnly


class DomainViewSet(viewsets.ModelViewSet):
    queryset = Domain.objects.all()
    serializer_class = DomainSerializer
    permission_classes = [IsAdminUser | ReadOnly]
    filter_backends = [SearchFilter, DjangoFilterBackend]
    filterset_class = DomainFilter
    search_fields = ['name', 'description']


class ProfessionViewSet(viewsets.ModelViewSet):
    queryset = Profession.objects.all()
    permission_classes = [IsAdminUser | ReadOnly]
    filter_backends = [SearchFilter, DjangoFilterBackend]
    filterset_class = ProfessionFilter
    search_fields = ['title']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProfessionSerializer
        return ProfessionDetailSerializer


class TechnologyViewSet(viewsets.ModelViewSet):
    serializer_class = TechnologySerializer
    queryset = Technology.objects.order_by('name')
    permission_classes = [IsAdminUser | ReadOnly]
    filter_backends = [SearchFilter, DjangoFilterBackend]
    filterset_class = TechnologyFilter
    search_fields = ['name', 'professions__title']


def health_check(request):
    """
    Endpoint simple pour les healthchecks Docker
    """
    return HttpResponse("ok", content_type="text/plain")
