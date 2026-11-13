from decouple import config
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.jobs.models import AgentEvent
from apps.organizations.models import Organization, OrganizationChannelCredential, Notification, UserNotification
from apps.organizations.serializers import OrganizationSerializer, NotificationSerializer, UserNotificationSerializer
from apps.organizations.permissions import IsOrganization
from services import linkedin_oauth


def _record_channel_event(org, action, actor=None, data=None):
    AgentEvent.objects.create(
        organization_id=org.pk, application=None,
        target_id=f'org:{org.pk}', action=action,
        actor='human' if actor else 'agent',
        input_data=data or {}, human_validator=actor,
    )


def _credential_status(cred):
    if cred is None:
        return 'disconnected'
    return cred.status


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

    @action(detail=True, methods=['get'], url_path='channels')
    def channels(self, request, pk=None):
        """Statut de connexion des canaux de diffusion (jamais de secret)."""
        org = self.get_object()
        creds = {c.channel: c for c in org.channel_credentials.all()}
        linkedin_cred = creds.get(OrganizationChannelCredential.Channel.LINKEDIN)
        emploi_cred = creds.get(OrganizationChannelCredential.Channel.EMPLOI_CM)
        return Response({'channels': [
            {'name': 'site_carriere', 'configured': True, 'status': 'connected', 'externalId': '', 'lastError': ''},
            {'name': 'linkedin', 'configured': bool(org.linkedin_page_url),
             'status': _credential_status(linkedin_cred),
             'externalId': linkedin_cred.external_id if linkedin_cred else '',
             'lastError': linkedin_cred.last_error if linkedin_cred else ''},
            {'name': 'emploi_cm', 'configured': bool(org.emploi_cm_account),
             'status': _credential_status(emploi_cred),
             'externalId': emploi_cred.external_id if emploi_cred else '',
             'lastError': emploi_cred.last_error if emploi_cred else ''},
        ]})

    @action(detail=True, methods=['get'], url_path='linkedin/connect')
    def linkedin_connect(self, request, pk=None):
        """Renvoie l'URL OAuth LinkedIn à ouvrir pour connecter la page de l'org."""
        org = self.get_object()
        url = linkedin_oauth.build_auth_url(request, org.pk, request.user.pk)
        if not url:
            return Response({'detail': 'LinkedIn non configuré côté plateforme (LINKEDIN_CLIENT_ID manquant).'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'authUrl': url})

    @action(detail=True, methods=['get'], url_path='linkedin/callback', permission_classes=[AllowAny])
    def linkedin_callback(self, request, pk=None):
        """Callback OAuth LinkedIn : échange le code, stocke le credential chiffré."""
        frontend_url = config('FRONTEND_CHANNELS_URL', default='').strip()

        def done(ok, error=''):
            if frontend_url:
                sep = '&' if '?' in frontend_url else '?'
                state = 'connected' if ok else 'error'
                return HttpResponseRedirect(f'{frontend_url}{sep}channel=linkedin&status={state}')
            return Response({'connected': ok, 'error': error},
                            status=status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST)

        error = request.GET.get('error')
        if error:
            return done(False, error)
        code, state = request.GET.get('code'), request.GET.get('state')
        if not code or not state:
            return done(False, 'missing_code_or_state')
        try:
            data = linkedin_oauth.verify_state(state)
        except ValueError:
            return done(False, 'invalid_state')
        if int(data.get('org') or 0) != int(pk):
            return done(False, 'org_mismatch')
        try:
            org = Organization.objects.get(pk=pk)
        except Organization.DoesNotExist:
            return done(False, 'org_not_found')

        try:
            tokens = linkedin_oauth.exchange_code(code, linkedin_oauth.callback_url(request, org.pk))
        except linkedin_oauth.LinkedInError as exc:
            return done(False, str(exc))

        access_token = tokens['access_token']
        urn = linkedin_oauth.resolve_organization_urn(access_token, org.linkedin_page_url or '')
        cred, _ = OrganizationChannelCredential.objects.get_or_create(
            organization=org, channel=OrganizationChannelCredential.Channel.LINKEDIN)
        cred.set_secret(access_token)
        if tokens.get('refresh_token'):
            cred.set_refresh_secret(tokens['refresh_token'])
        cred.external_id = urn or linkedin_oauth.vanity_name_from_url(org.linkedin_page_url or '')
        cred.status = OrganizationChannelCredential.Status.CONNECTED
        cred.last_error = ''
        expires_in = tokens.get('expires_in')
        cred.expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in)) if expires_in else None
        cred.save()
        _record_channel_event(org, 'channel.linkedin.connected',
                              data={'external_id': cred.external_id})
        return done(True)

    @action(detail=True, methods=['post'], url_path='channels/emploi_cm/connect')
    def emploi_cm_connect(self, request, pk=None):
        """Enregistre la clé API Emploi.cm de l'organisation (chiffrée)."""
        org = self.get_object()
        api_key = (request.data.get('api_key') or '').strip()
        external_id = (request.data.get('external_id') or org.emploi_cm_account or '').strip()
        if not api_key:
            return Response({'apiKey': ['Ce champ est obligatoire.']}, status=status.HTTP_400_BAD_REQUEST)

        cred, _ = OrganizationChannelCredential.objects.get_or_create(
            organization=org, channel=OrganizationChannelCredential.Channel.EMPLOI_CM)
        cred.set_secret(api_key)
        cred.external_id = external_id
        cred.status = OrganizationChannelCredential.Status.PENDING
        cred.last_error = ''

        base_url = config('EMPLOI_CM_BASE_URL', default='').strip()
        if base_url:
            try:
                import requests
                resp = requests.get(base_url, headers={'Authorization': f'Bearer {api_key}'}, timeout=10)
                cred.status = (OrganizationChannelCredential.Status.CONNECTED
                               if resp.status_code < 400 else OrganizationChannelCredential.Status.FAILED)
                if resp.status_code >= 400:
                    cred.last_error = 'Clé API refusée par Emploi.cm'
            except requests.RequestException:
                cred.status = OrganizationChannelCredential.Status.PENDING
        cred.save()
        _record_channel_event(org, 'channel.emploi_cm.connected', data={'status': cred.status})
        return Response({'name': 'emploi_cm', 'status': cred.status, 'externalId': cred.external_id})

    @action(detail=True, methods=['delete'], url_path='channels/<str:channel>')
    def channel_disconnect(self, request, channel=None, pk=None):
        """Déconnecte un canal (supprime le credential stocké)."""
        org = self.get_object()
        deleted, _ = org.channel_credentials.filter(channel=channel).delete()
        if not deleted:
            return Response({'detail': 'Canal non connecté.'}, status=status.HTTP_404_NOT_FOUND)
        _record_channel_event(org, f'channel.{channel}.disconnected')
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsOrganization]

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'organization'):
            return Notification.objects.none()
        return Notification.objects.filter(organization=user.organization).order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        qs = self.get_queryset().filter(is_read=False)
        return Response({'count': qs.count()})

    @action(detail=True, methods=['patch'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        notif = self.get_object()
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=['is_read'])
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'], url_path='mark-all-as-read')
    def mark_all_as_read(self, request):
        qs = self.get_queryset().filter(is_read=False)
        updated = qs.update(is_read=True)
        return Response({'updated': True, 'count': updated})

    def destroy(self, request, *args, **kwargs):
        """Permet de supprimer une notification"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'status': 'deleted'}, status=204)


class UserNotificationViewSet(viewsets.ModelViewSet):
    """ViewSet pour les notifications des candidats/utilisateurs"""
    serializer_class = UserNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retourne uniquement les notifications de l'utilisateur connecté"""
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return UserNotification.objects.none()
        return UserNotification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Compte les notifications non lues"""
        qs = self.get_queryset().filter(is_read=False)
        return Response({'count': qs.count()})

    @action(detail=True, methods=['patch'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        """Marque une notification comme lue"""
        notif = self.get_object()
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=['is_read'])
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'], url_path='mark-all-as-read')
    def mark_all_as_read(self, request):
        """Marque toutes les notifications comme lues"""
        qs = self.get_queryset().filter(is_read=False)
        updated = qs.update(is_read=True)
        return Response({'updated': True, 'count': updated})

    def destroy(self, request, *args, **kwargs):
        """Supprime une notification"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'status': 'deleted'}, status=204)
