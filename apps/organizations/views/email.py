import base64

from django.http import FileResponse, HttpResponse
from services.channel_crypto import decrypt_secret
from django.db import IntegrityError, transaction
from drf_spectacular.types import OpenApiTypes
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.authentication import PermissiveJWTAuthentication
from apps.jobs.models import JobOffer
from apps.organizations.models import RecruitmentEmailInbox, RecruitmentEmailMessage
from apps.organizations.serializers.email import (
    AssignEmailSerializer, EmailInboxSerializer, EmailMessageSerializer, EmailSyncSerializer,
    GmailConnectSerializer,
)
from services.recruitment_email import MailboxError, assign_message, audit, connect_gmail_inbox, test_inbox


class EmailInboxViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                        mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = EmailInboxSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [PermissiveJWTAuthentication]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        organization = getattr(self.request.user, 'organization', None)
        return RecruitmentEmailInbox.objects.filter(organization=organization).annotate(
            pending_assignment_count=Count('messages', filter=Q(messages__status='unassigned')),
            pending_analysis_count=Count('messages', filter=Q(messages__analysis_state__in=['pending', 'processing'])),
        ).order_by('pk')

    @extend_schema(request=GmailConnectSerializer,
                   responses={201: EmailInboxSerializer, 400: OpenApiResponse(description='Échange OAuth impossible : code d’erreur non sensible.')},
                   description=(
        'Connecte la boîte Gmail de l’organisation via un authorization code Google '
        '(consentement avec access_type=offline, prompt=consent et scope gmail.readonly). '
        'La connexion est vérifiée, activée et synchronisée périodiquement sans mot de passe. '
        'folder désigne le libellé Gmail surveillé (INBOX par défaut).'))
    @action(detail=False, methods=['post'], url_path='gmail-connect')
    def gmail_connect(self, request):
        organization = getattr(request.user, 'organization', None)
        if not organization:
            raise PermissionDenied('Un compte organisation est requis.')
        serializer = GmailConnectSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            inbox = connect_gmail_inbox(
                organization, serializer.validated_data['code'],
                serializer.validated_data.get('redirect_uri') or '',
                folder=serializer.validated_data['folder'],
                default_offer=serializer.validated_data.get('default_offer'),
                enabled=serializer.validated_data.get('enabled', True),
                actor=request.user)
        except MailboxError as exc:
            return Response({'errorCode': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EmailInboxSerializer(inbox, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(description=(
        'Connecte un dossier de candidatures de la boîte RH de l’organisation connectée. IMAP TLS 993, '
        'mot de passe d’application ; pour Gmail, préférer /gmail-connect/ (OAuth). '
        'Secret chiffré et jamais renvoyé. '
        'Créer désactivé, tester avec /test/, puis PATCH enabled=true. '
        'Dossier ASCII dédié recommandé. defaultOffer est optionnel et doit appartenir à l’organisation ; '
        'sans offre certaine, le message reste à rattacher. Lecture non destructive, y compris des emails déjà lus. '
        'Plusieurs dossiers/boîtes peuvent être connectés, une connexion par dossier.'))
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        organization = getattr(self.request.user, 'organization', None)
        if not organization:
            raise PermissionDenied('Un compte organisation est requis.')
        try:
            with transaction.atomic():
                inbox = serializer.save(organization=organization)
                audit(inbox, 'email.inbox_created', actor=self.request.user)
        except IntegrityError:
            raise ValidationError({'detail': 'Ce dossier de cette boîte est déjà connecté à votre organisation.'})

    def perform_update(self, serializer):
        with transaction.atomic():
            inbox = serializer.save()
            audit(inbox, 'email.inbox_updated', actor=self.request.user,
                  data={'fields': sorted(serializer.validated_data.keys() - {'secret', 'password'}), 'enabled': inbox.enabled})

    @extend_schema(request=None, responses={200: OpenApiResponse(description='Connexion TLS et dossier vérifiés sans modifier les emails.'),
                                           400: OpenApiResponse(description='Connexion impossible : code d’erreur non sensible.')})
    @action(detail=True, methods=['post'], url_path='test')
    def test_connection(self, request, pk=None):
        inbox = self.get_object()
        try:
            result = test_inbox(inbox)
        except MailboxError as exc:
            RecruitmentEmailInbox.objects.filter(pk=inbox.pk).update(error_code=str(exc), verified_at=None, enabled=False)
            return Response({'errorCode': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        audit(inbox, 'email.inbox_verified', actor=request.user)
        return Response(result)

    @extend_schema(request=None, responses={202: EmailSyncSerializer, 400: OpenApiResponse(description='Connexion non activée ou non vérifiée.'),
                                           503: OpenApiResponse(description='File de traitement indisponible ; synchronisation périodique réessaiera.')},
                   description='Demande une synchronisation asynchrone ; 202 ne signifie pas que l’import est terminé. Consulter lastSyncAt et errorCode.')
    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        inbox = self.get_object()
        if not inbox.enabled or not inbox.verified_at:
            raise ValidationError({'detail': 'Testez puis activez cette connexion avant de synchroniser.'})
        RecruitmentEmailInbox.objects.filter(pk=inbox.pk).update(next_sync_at=timezone.now())
        try:
            from apps.jobs.tasks import sync_recruitment_inbox
            sync_recruitment_inbox.delay(inbox.pk)
        except Exception:
            RecruitmentEmailInbox.objects.filter(pk=inbox.pk).update(error_code='queue_unavailable')
            return Response({'status': 'pending', 'errorCode': 'queue_unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'status': 'queued', 'inboxIds': [inbox.pk]}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses=EmailMessageSerializer(many=True), description=(
        'Messages de cette connexion uniquement. status=unassigned nécessite un rattachement humain. '
        'analysisState décrit la file email ; analysisStatus, matchScore et needsHumanReview reflètent le dossier réel. '
        'Aucun corps de message, pièce jointe brute ou secret n’est exposé.'))
    @action(detail=True, methods=['get'], url_path='messages')
    def messages(self, request, pk=None):
        inbox = self.get_object()
        queryset = inbox.messages.select_related('application__analysis').all()
        page = self.paginate_queryset(queryset)
        serializer = EmailMessageSerializer(page if page is not None else queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @extend_schema(responses={(200, 'message/rfc822'): OpenApiTypes.BINARY},
                   description='Télécharge le message original et ses pièces jointes en .eml, uniquement pour l’organisation propriétaire.')
    @action(detail=True, methods=['get'], url_path='messages/<int:message_id>/original')
    def download_original(self, request, pk=None, message_id=None):
        inbox = self.get_object()
        message = get_object_or_404(RecruitmentEmailMessage, pk=message_id, inbox=inbox)
        raw = decrypt_secret(message.raw_secret)
        if not raw:
            return Response({'detail': 'Original indisponible ; consultez la boîte source.'}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(base64.b64decode(raw), content_type='message/rfc822')
        response['Content-Disposition'] = 'attachment; filename="candidature.eml"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    @extend_schema(responses={(200, 'application/pdf'): OpenApiTypes.BINARY},
                   description='Téléchargement privé du CV PDF ; requiert le JWT de l’organisation propriétaire. Utiliser fetch authentifié puis un Blob.')
    @action(detail=True, methods=['get'], url_path='messages/<int:message_id>/resume', url_name='resume')
    def download_resume(self, request, pk=None, message_id=None):
        inbox = self.get_object()
        message = get_object_or_404(RecruitmentEmailMessage, pk=message_id, inbox=inbox)
        if not message.resume_file:
            return Response({'detail': 'Aucun CV PDF disponible.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            file = message.resume_file.open('rb')
        except FileNotFoundError:
            return Response({'detail': 'CV indisponible ; intervention requise.'}, status=status.HTTP_404_NOT_FOUND)
        response = FileResponse(file, as_attachment=True, filename='cv.pdf', content_type='application/pdf')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    @extend_schema(request=AssignEmailSerializer, responses={200: EmailMessageSerializer,
                                                            400: OpenApiResponse(description='Message inexploitable ou déjà rattaché.'),
                                                            404: OpenApiResponse(description='Message ou offre non autorisé.')})
    @action(detail=True, methods=['post'], url_path='messages/<int:message_id>/assign')
    def assign(self, request, pk=None, message_id=None):
        inbox = self.get_object()
        message = get_object_or_404(RecruitmentEmailMessage, pk=message_id, inbox=inbox)
        serializer = AssignEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offer = get_object_or_404(JobOffer, pk=serializer.validated_data['offer_id'], company_id=inbox.organization_id)
        try:
            message = assign_message(message.pk, offer, actor=request.user)
        except MailboxError as exc:
            raise ValidationError({'errorCode': str(exc)})
        return Response(EmailMessageSerializer(message).data)
