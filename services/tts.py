import base64
import hashlib
import io
import logging
import wave

from decouple import config
from django.core.cache import cache
from google.genai.errors import APIError
from google.genai.types import (
    GenerateContentConfig, PrebuiltVoiceConfig, SpeechConfig, VoiceConfig,
)

from services.offer_agent import OfferAgentError
from services.utils import generate_content_with_retry, get_genai_client

logger = logging.getLogger(__name__)

TTS_MODEL = config('GEMINI_TTS_MODEL', default='gemini-2.5-flash-preview-tts')
DEFAULT_VOICE = config('GEMINI_TTS_VOICE', default='Aoede')
MAX_TEXT_LENGTH = 4000
SAMPLE_RATE = 24000
_CACHE_TTL = 3600  # 1h — même texte/même voix = même audio


def pcm_to_wav(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    """Emballe du PCM 16-bit mono dans un conteneur WAV (jouable par <audio>)."""
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def synthesize_speech(text: str, voice: str = '') -> bytes:
    """Synthétise un texte en audio WAV via Gemini TTS. Lève OfferAgentError."""
    text = (text or '').strip()
    if not text:
        raise OfferAgentError('empty_text', 'Aucun texte à synthétiser.', 400)
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
    voice = (voice or DEFAULT_VOICE).strip()

    cache_key = 'tts:' + hashlib.sha256(f'{voice}:{text}'.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return base64.b64decode(cached)

    try:
        response = generate_content_with_retry(get_genai_client(), 
            model=TTS_MODEL,
            contents=text,
            config=GenerateContentConfig(
                response_modalities=['AUDIO'],
                speech_config=SpeechConfig(
                    voice_config=VoiceConfig(
                        prebuilt_voice_config=PrebuiltVoiceConfig(voice_name=voice))),
            ),
        )
        audio = response.candidates[0].content.parts[0].inline_data
        wav = pcm_to_wav(audio.data)
    except APIError as exc:
        logger.warning('TTS failed: %s', exc.code)
        if exc.code == 429:
            raise OfferAgentError('tts_rate_limited', 'Quota vocal atteint. Réessayez plus tard.', 429) from exc
        if exc.code in (401, 403):
            raise OfferAgentError('ai_authentication_failed', 'Le fournisseur IA refuse l’accès.', 503) from exc
        if exc.code == 404:
            raise OfferAgentError('ai_model_unavailable', 'La synthèse vocale est indisponible.', 503) from exc
        raise OfferAgentError('ai_provider_unavailable', 'Le service vocal est indisponible.', 503) from exc
    except (IndexError, AttributeError, TypeError) as exc:
        raise OfferAgentError('ai_invalid_response', 'Réponse audio inexploitable. Réessayez.') from exc

    cache.set(cache_key, base64.b64encode(wav).decode(), _CACHE_TTL)
    return wav
