import logging

import requests
from decouple import config
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.jobs.models import AgentEvent
from apps.organizations.models import OrganizationChannelCredential as ChannelCred
from services import linkedin_oauth

logger = logging.getLogger(__name__)

KNOWN_CHANNELS = ('site_carriere', 'linkedin', 'emploi_cm')


def _audit(org, action, *, offer=None, data=None):
    AgentEvent.objects.create(
        organization_id=org.pk, application=None,
        target_id=f'offer:{offer.pk}' if offer else f'org:{org.pk}',
        action=action, actor='agent', input_data=data or {},
    )


def _notify_hr(org, subject, message):
    recipient = (org.hr_alert_email or org.account.email or org.email or '').strip()
    if not recipient:
        return
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=True)
    except Exception:  # noqa: BLE001
        logger.warning('Unable to notify HR for org %s', org.pk)


def _offer_post_text(offer) -> str:
    org_name = getattr(offer.company, 'name', '')
    return (f'{offer.title}\n{org_name} — {offer.location}\n\n'
            f'{(offer.description or "")[:1500]}')


def _career_site_publish(offer) -> dict:
    """Canal 'site carrière' : l'offre publiée est servie par l'API de la plateforme."""
    return {
        'name': 'site_carriere',
        'state': 'published',
        'url': f'/api/jobs/offers/{offer.pk}/',
        'published_at': offer.published_at.isoformat() if offer.published_at else None,
    }


_career_site_publish.channel_name = 'site_carriere'


def _linkedin_failed(org, offer, error, *, cred=None):
    if cred is not None:
        cred.last_error = error
        cred.save(update_fields=['last_error', 'updated_at'])
    _audit(org, 'channel.linkedin.publish_failed', offer=offer, data={'error': error})
    return {'name': 'linkedin', 'state': 'failed', 'error': error}


def _linkedin_publish(offer) -> dict:
    org = offer.company
    if not org.linkedin_page_url:
        return _linkedin_failed(org, offer, 'Page LinkedIn non renseignée (linkedinPageUrl)')
    cred = org.channel_credentials.filter(channel=ChannelCred.Channel.LINKEDIN).first()
    if cred is None or cred.status != ChannelCred.Status.CONNECTED:
        return _linkedin_failed(org, offer, 'Canal non connecté — connectez votre compte dans Paramètres', cred=cred)
    if not cred.external_id:
        return _linkedin_failed(org, offer, 'Page LinkedIn non résolue (identifiant externe manquant)', cred=cred)

    author = (cred.external_id if cred.external_id.startswith('urn:')
              else f'urn:li:organization:{cred.external_id}')
    text = _offer_post_text(offer)

    # Refresh proactif si le token est expiré
    if cred.expires_at and cred.expires_at <= timezone.now():
        if not _refresh_linkedin_token(org, offer, cred):
            return _linkedin_failed(org, offer, 'Token LinkedIn expiré — reconnectez votre compte', cred=cred)

    try:
        post_urn = linkedin_oauth.publish_post(cred.get_secret(), author, text)
    except linkedin_oauth.LinkedInError as exc:
        if str(exc) != 'token_expired' or not _refresh_linkedin_token(org, offer, cred):
            if str(exc) == 'token_expired':
                return _linkedin_failed(org, offer, 'Token LinkedIn expiré — reconnectez votre compte', cred=cred)
            return _linkedin_failed(org, offer, 'Publication refusée par LinkedIn', cred=cred)
        try:
            post_urn = linkedin_oauth.publish_post(cred.get_secret(), author, text)
        except linkedin_oauth.LinkedInError:
            return _linkedin_failed(org, offer, 'Publication refusée par LinkedIn', cred=cred)

    cred.status = ChannelCred.Status.CONNECTED
    cred.last_error = ''
    cred.save(update_fields=['status', 'last_error', 'updated_at'])
    _audit(org, 'channel.linkedin.published', offer=offer, data={'post': post_urn})
    return {'name': 'linkedin', 'state': 'published',
            'url': f'https://www.linkedin.com/feed/update/{post_urn}' if post_urn else ''}


def _refresh_linkedin_token(org, offer, cred) -> bool:
    """Tente un refresh LinkedIn ; passe le credential à 'expired' et alerte RH si échec."""
    refresh = cred.get_refresh_secret()
    if not refresh:
        cred.status = ChannelCred.Status.EXPIRED
        cred.last_error = 'Token expiré sans refresh token'
        cred.save(update_fields=['status', 'last_error', 'updated_at'])
        _notify_hr(org, 'Connexion LinkedIn expirée',
                   f"La connexion LinkedIn de {org.name} a expiré. Reconnectez la page dans Paramètres > Canaux.")
        _audit(org, 'channel.linkedin.expired', offer=offer)
        return False
    try:
        tokens = linkedin_oauth.refresh_access_token(refresh)
    except linkedin_oauth.LinkedInError:
        cred.status = ChannelCred.Status.EXPIRED
        cred.last_error = 'Refresh refusé par LinkedIn'
        cred.save(update_fields=['status', 'last_error', 'updated_at'])
        _notify_hr(org, 'Connexion LinkedIn expirée',
                   f"La connexion LinkedIn de {org.name} a expiré. Reconnectez la page dans Paramètres > Canaux.")
        _audit(org, 'channel.linkedin.expired', offer=offer)
        return False
    cred.set_secret(tokens['access_token'])
    if tokens.get('refresh_token'):
        cred.set_refresh_secret(tokens['refresh_token'])
    expires_in = tokens.get('expires_in')
    cred.expires_at = (timezone.now() + timezone.timedelta(seconds=int(expires_in))) if expires_in else None
    cred.status = ChannelCred.Status.CONNECTED
    cred.save()
    return True


_linkedin_publish.channel_name = 'linkedin'


def _emploi_cm_failed(org, offer, error, *, cred=None):
    if cred is not None:
        cred.last_error = error
        cred.save(update_fields=['last_error', 'updated_at'])
    _audit(org, 'channel.emploi_cm.publish_failed', offer=offer, data={'error': error})
    return {'name': 'emploi_cm', 'state': 'failed', 'error': error}


def _emploi_cm_publish(offer) -> dict:
    org = offer.company
    if not org.emploi_cm_account:
        return _emploi_cm_failed(org, offer, 'Compte Emploi.cm non renseigné (emploiCmAccount)')
    cred = org.channel_credentials.filter(channel=ChannelCred.Channel.EMPLOI_CM).first()
    if cred is None or cred.status not in (ChannelCred.Status.CONNECTED, ChannelCred.Status.PENDING):
        return _emploi_cm_failed(org, offer, 'Canal non connecté — connectez votre compte dans Paramètres', cred=cred)

    api_key = cred.get_secret()
    if not api_key:
        return _emploi_cm_failed(org, offer, 'Clé API Emploi.cm illisible — reconnectez le canal', cred=cred)
    base_url = config('EMPLOI_CM_BASE_URL', default='').strip()
    if not base_url:
        return _emploi_cm_failed(org, offer, 'API Emploi.cm non configurée côté plateforme', cred=cred)

    payload = {
        'title': offer.title,
        'company': org.name,
        'account': cred.external_id or org.emploi_cm_account,
        'description': offer.description or '',
        'location': offer.location or '',
        'jobType': offer.job_type,
        'experienceLevel': offer.experience_level,
        'salary': offer.salary or '',
        'currency': offer.currency or '',
        'applicationUrl': offer.application_url or '',
        'expiresAt': offer.expires_at.date().isoformat() if offer.expires_at else None,
    }
    try:
        resp = requests.post(f'{base_url.rstrip("/")}/jobs', json=payload,
                             headers={'Authorization': f'Bearer {api_key}'}, timeout=20)
    except requests.RequestException:
        return _emploi_cm_failed(org, offer, 'API Emploi.cm injoignable', cred=cred)

    if resp.status_code in (401, 403):
        cred.status = ChannelCred.Status.FAILED
        cred.save(update_fields=['status', 'updated_at'])
        return _emploi_cm_failed(org, offer, 'Clé API Emploi.cm refusée', cred=cred)
    if resp.status_code not in (200, 201, 202):
        return _emploi_cm_failed(org, offer, 'Publication refusée par Emploi.cm', cred=cred)

    cred.status = ChannelCred.Status.CONNECTED
    cred.last_error = ''
    cred.save(update_fields=['status', 'last_error', 'updated_at'])
    url = ''
    try:
        url = resp.json().get('url', '') or resp.json().get('jobUrl', '')
    except ValueError:
        pass
    _audit(org, 'channel.emploi_cm.published', offer=offer, data={'status_code': resp.status_code})
    return {'name': 'emploi_cm', 'state': 'published' if resp.status_code != 202 else 'queued', 'url': url}


_emploi_cm_publish.channel_name = 'emploi_cm'

CHANNEL_ADAPTERS = [_career_site_publish, _linkedin_publish, _emploi_cm_publish]


def distribute_offer(offer, channels=None) -> list[dict]:
    """Diffuse une offre sur les canaux choisis par l'organisation.

    La liste par défaut vient de `organization.preferred_channels` ; 'site_carriere'
    est toujours diffusé. Ne renvoie jamais 'published' pour un canal externe non
    confirmé : les adaptateurs non configurés renvoient 'failed' avec le motif.
    """
    if channels is None:
        wanted = set(offer.company.preferred_channels or ()) | {'site_carriere'}
    else:
        wanted = set(channels)
    adapters = {a.channel_name: a for a in CHANNEL_ADAPTERS}
    results = []
    for name in [n for n in KNOWN_CHANNELS if n in wanted]:
        try:
            results.append(adapters[name](offer))
        except Exception:  # noqa: BLE001 - un canal en échec ne doit pas bloquer les autres
            logger.warning('Distribution failed for channel %s on offer %s', name, offer.pk)
            results.append({'name': name, 'state': 'failed', 'error': 'Erreur interne du canal'})
    results += [{'name': n, 'state': 'failed', 'error': 'Canal inconnu'} for n in sorted(wanted - set(KNOWN_CHANNELS))]
    return results


def publish_offer(offer) -> dict:
    """Bascule l'offre en statut publié et lance la diffusion multi-canaux."""
    if offer.status != offer.Status.PUBLISHED:
        offer.status = offer.Status.PUBLISHED
        offer.published_at = timezone.now()
        offer.save(update_fields=['status', 'published_at', 'updated_at'])
    elif offer.published_at is None:
        offer.published_at = timezone.now()
        offer.save(update_fields=['published_at', 'updated_at'])
    channels = distribute_offer(offer)
    return {'status': offer.status, 'channels': channels}
