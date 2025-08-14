from logging import getLogger
from smtplib import SMTPException

from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.filters import TechnologyFilter, ProfessionFilter, DomainFilter
from apps.core.models import Profession, Technology, Domain
from apps.core.serializers import ProfessionSerializer, ProfessionDetailSerializer, TechnologySerializer, \
    DomainSerializer
from wib_challenge.permissions import ReadOnly
from .serializers import ContactSerializer

logger = getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des domaines",
        description="Récupère la liste des domaines d'activité avec filtres et recherche",
        tags=["Domaines"]
    ),
    create=extend_schema(
        summary="Créer un domaine",
        description="Crée un nouveau domaine d'activité (admin uniquement)",
        tags=["Domaines"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un domaine",
        description="Récupère les détails d'un domaine spécifique",
        tags=["Domaines"]
    ),
    update=extend_schema(
        summary="Mettre à jour un domaine",
        description="Met à jour un domaine d'activité (admin uniquement)",
        tags=["Domaines"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'un domaine",
        description="Met à jour partiellement un domaine (admin uniquement)",
        tags=["Domaines"]
    ),
    destroy=extend_schema(
        summary="Supprimer un domaine",
        description="Supprime un domaine d'activité (admin uniquement)",
        tags=["Domaines"]
    )
)
class DomainViewSet(viewsets.ModelViewSet):
    queryset = Domain.objects.all()
    serializer_class = DomainSerializer
    permission_classes = [IsAdminUser | ReadOnly]
    filter_backends = [SearchFilter, DjangoFilterBackend]
    filterset_class = DomainFilter
    search_fields = ['name', 'description']


@extend_schema_view(
    list=extend_schema(
        summary="Liste des professions",
        description="Récupère la liste des professions avec filtres et recherche",
        tags=["Professions"]
    ),
    create=extend_schema(
        summary="Créer une profession",
        description="Crée une nouvelle profession (admin uniquement)",
        tags=["Professions"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une profession",
        description="Récupère les détails d'une profession avec ses technologies associées",
        tags=["Professions"]
    ),
    update=extend_schema(
        summary="Mettre à jour une profession",
        description="Met à jour une profession (admin uniquement)",
        tags=["Professions"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'une profession",
        description="Met à jour partiellement une profession (admin uniquement)",
        tags=["Professions"]
    ),
    destroy=extend_schema(
        summary="Supprimer une profession",
        description="Supprime une profession (admin uniquement)",
        tags=["Professions"]
    )
)
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


@extend_schema_view(
    list=extend_schema(
        summary="Liste des technologies",
        description="Récupère la liste des technologies avec filtres et recherche",
        tags=["Technologies"]
    ),
    create=extend_schema(
        summary="Créer une technologie",
        description="Crée une nouvelle technologie (admin uniquement)",
        tags=["Technologies"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une technologie",
        description="Récupère les détails d'une technologie avec ses professions associées",
        tags=["Technologies"]
    ),
    update=extend_schema(
        summary="Mettre à jour une technologie",
        description="Met à jour une technologie (admin uniquement)",
        tags=["Technologies"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'une technologie",
        description="Met à jour partiellement une technologie (admin uniquement)",
        tags=["Technologies"]
    ),
    destroy=extend_schema(
        summary="Supprimer une technologie",
        description="Supprime une technologie (admin uniquement)",
        tags=["Technologies"]
    )
)
class TechnologyViewSet(viewsets.ModelViewSet):
    serializer_class = TechnologySerializer
    queryset = Technology.objects.order_by('name')
    permission_classes = [IsAdminUser | ReadOnly]
    filter_backends = [SearchFilter, DjangoFilterBackend]
    filterset_class = TechnologyFilter
    search_fields = ['name', 'professions__title']


@extend_schema(
    summary="Health Check",
    description="Endpoint de vérification de l'état de l'API",
    tags=["Système"]
)
def health_check(request):
    """
    Endpoint simple pour les healthchecks Docker
    """
    return HttpResponse("ok", content_type="text/plain")


class ContactView(APIView):
    """Vue pour gérer les messages de contact"""

    def post(self, request):
        """Envoie un email de contact"""
        serializer = ContactSerializer(data=request.data)

        if serializer.is_valid():
            try:
                serializer.send_email()

                return Response({
                    'success': True,
                    'message': 'Votre message a été envoyé avec succès. Nous vous répondrons dans les plus brefs délais.'
                }, status=status.HTTP_200_OK)

            except SMTPException as e:
                logger.error(f"Erreur lors de l'envoi de l'email de contact: {e}")
                return Response({
                    'success': False,
                    'message': 'Une erreur est survenue lors de l\'envoi de votre message. Veuillez réessayer plus tard.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except Exception as e:
                logger.error(f"Erreur inattendue lors de l'envoi du contact: {e}")
                return Response({
                    'success': False,
                    'message': 'Une erreur inattendue est survenue. Veuillez réessayer plus tard.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': False,
            'message': 'Les données fournies ne sont pas valides.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
