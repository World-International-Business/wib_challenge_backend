import logging
import secrets
from urllib.parse import urlencode, urlparse

import requests
from decouple import config
from django.core.signing import TimestampSigner
from django.utils import timezone

logger = logging.getLogger(__name__)

AUTHORIZE_URL = 'https://www.linkedin.com/oauth/v2/authorization'
TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'
POSTS_URL = 'https://api.linkedin.com/rest/posts'
ORG_LOOKUP_URL = 'https://api.linkedin.com/v2/organizationsLookup'
SCOPES = 'w_organization_social r_organization_social'
STATE_MAX_AGE = 600  # 10 minutes


class LinkedInError(Exception):
    pass


def _signer() -> TimestampSigner:
    return TimestampSigner(salt='linkedin-oauth')


def build_state(organization_id: int, user_id: int) -> str:
    return _signer().sign_object({'org': organization_id, 'user': user_id, 'nonce': secrets.token_hex(8)})


def verify_state(state: str) -> dict:
    """Retourne {org, user, nonce} ou lève ValueError (signature/expiration invalide)."""
    try:
        return _signer().unsign_object(state, max_age=STATE_MAX_AGE)
    except Exception as exc:
        raise ValueError('state invalide') from exc


def callback_url(request, organization_id: int) -> str:
    return request.build_absolute_uri(f'/api/organizations/{organization_id}/linkedin/callback/')


def build_auth_url(request, organization_id: int, user_id: int) -> str:
    client_id = config('LINKEDIN_CLIENT_ID', default='').strip()
    if not client_id:
        return ''
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': callback_url(request, organization_id),
        'state': build_state(organization_id, user_id),
        'scope': SCOPES,
    }
    return f'{AUTHORIZE_URL}?{urlencode(params)}'


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Échange le code OAuth contre un access token. Lève LinkedInError."""
    try:
        resp = requests.post(TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': config('LINKEDIN_CLIENT_ID', default=''),
            'client_secret': config('LINKEDIN_CLIENT_SECRET', default=''),
        }, timeout=15)
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise LinkedInError('Echange du code impossible') from exc
    if resp.status_code != 200 or not payload.get('access_token'):
        logger.warning('LinkedIn token exchange failed: status=%s error=%s', resp.status_code, payload.get('error'))
        raise LinkedInError("LinkedIn a refusé l'échange du code")
    return payload


def refresh_access_token(refresh_token: str) -> dict:
    """Rafraîchit un access token LinkedIn. Lève LinkedInError."""
    try:
        resp = requests.post(TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': config('LINKEDIN_CLIENT_ID', default=''),
            'client_secret': config('LINKEDIN_CLIENT_SECRET', default=''),
        }, timeout=15)
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise LinkedInError('Refresh du token impossible') from exc
    if resp.status_code != 200 or not payload.get('access_token'):
        raise LinkedInError('LinkedIn a refusé le refresh')
    return payload


def vanity_name_from_url(page_url: str) -> str:
    """linkedin.com/company/acme-corp/ -> acme-corp"""
    parts = [p for p in urlparse(page_url or '').path.split('/') if p]
    return parts[1] if len(parts) >= 2 and parts[0] == 'company' else (parts[0] if parts else '')


def resolve_organization_urn(access_token: str, page_url: str) -> str:
    """Résout le URN de la page entreprise (urn:li:organization:{id}). Chaîne vide si échec."""
    vanity = vanity_name_from_url(page_url)
    if not vanity:
        return ''
    try:
        resp = requests.get(ORG_LOOKUP_URL, params={'vanityName': vanity},
                            headers={'Authorization': f'Bearer {access_token}'}, timeout=15)
        if resp.status_code == 200:
            results = resp.json().get('results', [])
            if results:
                return f"urn:li:organization:{results[0]['id']}"
    except (requests.RequestException, ValueError, KeyError):
        pass
    return ''


def publish_post(access_token: str, author_urn: str, text: str, link: str = '') -> str:
    """Publie un post sur la page organisation. Retourne le URN du post. Lève LinkedInError."""
    post = {
        'author': author_urn,
        'commentary': text,
        'visibility': 'PUBLIC',
        'distribution': {'feedDistribution': 'MAIN_FEED', 'targetEntities': [], 'thirdPartyDistributionChannels': []},
        'lifecycleState': 'PUBLISHED',
        'isReshareDisabledByAuthor': False,
    }
    if link:
        post['content'] = {'article': {'source': link, 'title': text[:200]}}
    try:
        resp = requests.post(POSTS_URL, json=post, timeout=20, headers={
            'Authorization': f'Bearer {access_token}',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202405',
        })
    except requests.RequestException as exc:
        raise LinkedInError('Publication LinkedIn injoignable') from exc
    if resp.status_code == 401:
        raise LinkedInError('token_expired')
    if resp.status_code not in (200, 201):
        logger.warning('LinkedIn publish failed: status=%s body=%s', resp.status_code, resp.text[:300])
        raise LinkedInError('Publication refusée par LinkedIn')
    return resp.headers.get('x-restli-id', '')
