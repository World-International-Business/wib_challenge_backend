import json
import secrets
from datetime import timedelta

import requests
from django.conf import settings


class DailyError(RuntimeError):
    pass


def _config():
    api_key = getattr(settings, 'DAILY_API_KEY', '')
    domain = getattr(settings, 'DAILY_DOMAIN', '').strip().rstrip('/')
    if not api_key or not domain:
        raise DailyError('DAILY_API_KEY et DAILY_DOMAIN doivent être configurées.')
    return api_key, domain


def _request(method, path, **kwargs):
    api_key, _ = _config()
    try:
        response = requests.request(
            method,
            f'https://api.daily.co/v1{path}',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            timeout=20,
            **kwargs,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DailyError(f'Erreur Daily : {exc}') from exc
    return response.json() if response.content else {}


def ensure_room(interview):
    _, domain = _config()
    if interview.daily_room_name:
        return interview
    room_name = f'wib-interview-{interview.pk}-{secrets.token_urlsafe(10).lower()}'
    properties = {
        'enable_recording': 'cloud',
        'start_video_off': False,
        'start_audio_off': False,
        'max_participants': 2,
        'exp': int((interview.scheduled_at + timedelta(minutes=interview.duration_minutes + 60)).timestamp()),
    }
    _request('POST', '/rooms', json={'name': room_name, 'properties': properties})
    interview.daily_room_name = room_name
    interview.daily_room_url = f'{domain}/{room_name}'
    interview.save(update_fields=['daily_room_name', 'daily_room_url'])
    return interview


def create_meeting_token(interview, *, is_owner):
    ensure_room(interview)
    properties = {
        'room_name': interview.daily_room_name,
        'is_owner': is_owner,
        'exp': int((interview.scheduled_at + timedelta(minutes=interview.duration_minutes + 60)).timestamp()),
    }
    return _request('POST', '/meeting-tokens', json={'properties': properties})['token']


def start_recording(interview):
    return _request('POST', f'/rooms/{interview.daily_room_name}/recordings/start')


def stop_recording(interview):
    return _request('POST', f'/rooms/{interview.daily_room_name}/recordings/stop')


def analyze_transcript(transcript):
    if not transcript.strip():
        raise DailyError('La transcription est vide.')
    from challenges.corrector.utils import get_genai_client

    client = get_genai_client()
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=(
            'Analyse cette transcription d’entretien professionnel en français. '
            'Retourne uniquement un JSON avec les clés summary, strengths, risks, '
            'skills, follow_up_questions et recommendation. Ne déduis aucun élément '
            'sensible ou protégé et présente la recommandation comme une aide, jamais '
            'comme une décision automatique.\n\nTRANSCRIPTION:\n' + transcript
        ),
    )
    try:
        return json.loads(response.text)
    except (TypeError, json.JSONDecodeError):
        return {'summary': response.text}
