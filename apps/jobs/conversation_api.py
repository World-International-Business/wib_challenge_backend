import logging

from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.jobs.agent_api import recruiter_organization
from apps.jobs.agent_serializers import (
    AssistantMessageResponseSerializer, ConversationMessageInputSerializer,
    ConversationMessageSerializer, OfferConversationDetailSerializer,
    OfferConversationListSerializer, PublishResponseSerializer,
)
from apps.jobs.models import AgentEvent, ConversationMessage, OfferConversation
from services.offer_agent import OfferAgentError, OFFER_AGENT_MODEL, publish_conversation_offer, run_offer_agent

logger = logging.getLogger(__name__)


class OfferAgentThrottle(UserRateThrottle):
    """Limite les appels à l'agent LLM."""
    rate = '30/min'


def scoped_conversations(user):
    return OfferConversation.objects.filter(organization=recruiter_organization(user), user=user)


def agent_error_response(exc: OfferAgentError):
    return Response({'error': str(exc), 'code': exc.code}, status=exc.status_code)


def run_agent_and_respond(conversation, request, user_message=None):
    """Stocke la réponse de l'agent, journalise et formate la réponse API."""
    try:
        message = run_offer_agent(conversation)
    except OfferAgentError as exc:
        if user_message is not None:
            user_message.delete()
        return agent_error_response(exc)
    AgentEvent.objects.create(
        organization=conversation.organization, actor='agent', action='offer_agent.reply',
        target_id=str(conversation.pk), model_version=OFFER_AGENT_MODEL,
        input_data={'message_id': message.pk})
    conversation.refresh_from_db(fields=['state'])
    return Response({
        'message': ConversationMessageSerializer(message).data,
        'state': conversation.state,
    })


@extend_schema_view(
    get=extend_schema(tags=['Agent d\'offres'], responses=OfferConversationListSerializer(many=True)),
    post=extend_schema(tags=['Agent d\'offres'], request=ConversationMessageInputSerializer, responses=OfferConversationDetailSerializer),
)
class OfferConversationListCreate(generics.ListCreateAPIView):
    """Liste les conversations (brouillons) de l'utilisateur et en crée une nouvelle."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return OfferConversation.objects.none()
        return scoped_conversations(self.request.user).prefetch_related('messages')

    def get_serializer_class(self):
        return OfferConversationDetailSerializer if self.request.method == 'POST' else OfferConversationListSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        organization = recruiter_organization(request.user)
        conversation = OfferConversation.objects.create(organization=organization, user=request.user)
        if request.data.get('content'):
            serializer = ConversationMessageInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_message = ConversationMessage.objects.create(
                conversation=conversation, role=ConversationMessage.Role.USER,
                content=serializer.validated_data['content'])
            response = run_agent_and_respond(conversation, request, user_message=user_message)
            if response.status_code >= 400:
                return response
        return Response(OfferConversationDetailSerializer(conversation).data, status=201)


@extend_schema_view(
    get=extend_schema(tags=['Agent d\'offres'], responses=OfferConversationDetailSerializer),
    delete=extend_schema(tags=['Agent d\'offres']),
)
class OfferConversationDetail(generics.RetrieveDestroyAPIView):
    """Détail d'une conversation avec tout son historique ; DELETE supprime le brouillon."""
    permission_classes = [IsAuthenticated]
    serializer_class = OfferConversationDetailSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return OfferConversation.objects.none()
        return scoped_conversations(self.request.user).prefetch_related('messages')


@extend_schema_view(post=extend_schema(tags=['Agent d\'offres'], request=ConversationMessageInputSerializer, responses=AssistantMessageResponseSerializer))
class ConversationMessageCreate(APIView):
    """Envoie un message utilisateur et renvoie la réponse de l'agent (blocs typés)."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [OfferAgentThrottle]

    @transaction.atomic
    def post(self, request, pk):
        conversation = get_object_or_404(scoped_conversations(request.user), pk=pk)
        if conversation.state in (OfferConversation.State.APPROVED, OfferConversation.State.PUBLISHED):
            return Response({'error': 'Conversation clôturée : l’offre a déjà été validée.', 'code': 'conversation_closed'}, status=409)
        serializer = ConversationMessageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_message = ConversationMessage.objects.create(
            conversation=conversation, role=ConversationMessage.Role.USER,
            content=serializer.validated_data['content'])
        return run_agent_and_respond(conversation, request, user_message=user_message)


@extend_schema_view(patch=extend_schema(tags=['Agent d\'offres'], request=ConversationMessageInputSerializer, responses=AssistantMessageResponseSerializer))
class ConversationMessageEdit(APIView):
    """Modifie un message utilisateur passé : tronque l'historique à ce point et régénère."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [OfferAgentThrottle]

    @transaction.atomic
    def patch(self, request, pk, message_id):
        conversation = get_object_or_404(scoped_conversations(request.user), pk=pk)
        message = get_object_or_404(conversation.messages, pk=message_id, role=ConversationMessage.Role.USER)
        serializer = ConversationMessageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message.content = serializer.validated_data['content']
        message.save(update_fields=['content'])
        conversation.messages.filter(pk__gt=message.pk).delete()
        conversation.draft = {}
        conversation.state = OfferConversation.State.COLLECTING
        conversation.save(update_fields=['draft', 'state', 'updated_at'])
        return run_agent_and_respond(conversation, request)


@extend_schema_view(post=extend_schema(tags=['Agent d\'offres'], responses=PublishResponseSerializer))
class ConversationApprove(APIView):
    """Valide la fiche : crée l'offre et la publie avec la diffusion multi-canaux."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        from services.offer_distribution import publish_offer

        conversation = get_object_or_404(scoped_conversations(request.user), pk=pk)
        try:
            offer = publish_conversation_offer(conversation)
        except OfferAgentError as exc:
            return agent_error_response(exc)
        conversation.state = OfferConversation.State.PUBLISHING
        conversation.save(update_fields=['state', 'updated_at'])
        result = publish_offer(offer)
        conversation.state = OfferConversation.State.PUBLISHED
        conversation.save(update_fields=['state', 'updated_at'])
        ConversationMessage.objects.create(
            conversation=conversation, role=ConversationMessage.Role.ASSISTANT,
            content='Offre validée et diffusée.',
            blocks=[{'type': 'confirmation', 'data': {'offer_id': offer.pk}},
                    {'type': 'channel_plan', 'data': {'channels': result['channels']}}])
        AgentEvent.objects.create(
            organization=conversation.organization, actor='human', human_validator=request.user,
            action='offer.approved', target_id=str(offer.pk), input_data={'conversation_id': conversation.pk})
        return Response({'offer_id': offer.pk, **result})
