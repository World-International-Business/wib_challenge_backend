import logging
from decouple import config
from django.utils import timezone

logger = logging.getLogger(__name__)

KNOWN_CHANNELS = ('site_carriere', 'linkedin', 'emploi_cm')


def _career_site_publish(offer) -> dict:
    """Canal 'site carrière' : l'offre publiée est servie par l'API de la plateforme."""
    return {
        'name': 'site_carriere',
        'state': 'published',
        'url': f'/api/jobs/offers/{offer.pk}/',
        'published_at': offer.published_at.isoformat() if offer.published_at else None,
    }


_career_site_publish.channel_name = 'site_carriere'


def _linkedin_publish(offer) -> dict:
    org = offer.company
    if not config('LINKEDIN_API_TOKEN', default='').strip():
        return {'name': 'linkedin', 'state': 'failed', 'error': 'Canal non configuré (LINKEDIN_API_TOKEN manquant)'}
    if not org.linkedin_page_url:
        return {'name': 'linkedin', 'state': 'failed', 'error': 'Page LinkedIn non renseignée (linkedinPageUrl)'}
    # TODO: implémenter l'appel HTTP réel LinkedIn (OAuth + UGC posts sur la page)
    return {'name': 'linkedin', 'state': 'queued', 'page': org.linkedin_page_url}


_linkedin_publish.channel_name = 'linkedin'


def _emploi_cm_publish(offer) -> dict:
    org = offer.company
    if not config('EMPLOI_CM_API_TOKEN', default='').strip():
        return {'name': 'emploi_cm', 'state': 'failed', 'error': 'Canal non configuré (EMPLOI_CM_API_TOKEN manquant)'}
    if not org.emploi_cm_account:
        return {'name': 'emploi_cm', 'state': 'failed', 'error': 'Compte Emploi.cm non renseigné (emploiCmAccount)'}
    # TODO: implémenter l'appel HTTP réel Emploi.cm
    return {'name': 'emploi_cm', 'state': 'queued', 'account': org.emploi_cm_account}


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
