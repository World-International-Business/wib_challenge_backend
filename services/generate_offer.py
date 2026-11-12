from decouple import UndefinedValueError
from django.conf import settings
from google.genai.errors import APIError
from google.genai.types import GenerateContentConfigDict
from httpx import RequestError, TimeoutException
from pydantic import BaseModel, Field, ValidationError

from apps.jobs.models import JobCategory
from services.utils import get_genai_client


class OfferGenerationError(Exception):
    def __init__(self, code, message, status_code=502):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class OfferInfo(BaseModel):
    title: str | None = None
    poste: str | None = Field(None, description="Intitulé exact d'une catégorie existante, ou une nouvelle catégorie courte si aucune ne convient")
    description: str | None = None
    responsibilities: str | None = None
    requirements: str | None = None
    benefits: str | None = None
    analyze: str | None = None
    skills: list[str] | None = Field(None, description='Technologies/competences de deux mots max')


def generate_offer(prompt_description: str, data: dict):
    offer = OfferInfo(**data)
    categories = list(JobCategory.objects.order_by('title').values_list('title', flat=True))
    categories_line = f"Catégories disponibles : {', '.join(categories)}\n" if categories else ''
    prompt = (
        "En tant qu'expert en Ressources Humaines\n"
        "Génère une offre d'emploi détaillée à partir des informations suivantes :\n"
        f"Titre : {offer.title or 'Non spécifié'}\n"
        f"Contexte : {prompt_description}\n"
        f"Poste : {offer.poste or 'Non spécifié'}\n"
        f"{categories_line}"
        f"Description : {offer.description or 'Non spécifié'}\n"
        f"Responsabilités : {offer.responsibilities or 'Non spécifié'}\n"
        f"Exigences : {offer.requirements or 'Non spécifié'}\n"
        f"Avantages : {offer.benefits or 'Non spécifié'}\n"
        f"Compétences : {', '.join(offer.skills or []) or 'Non spécifiées'}\n"
        "Structure l'offre de façon professionnelle et attractive.\n"
        "Dans le champ `poste`, choisis l'intitulé exact de la catégorie disponible la plus pertinente ; propose un intitulé court seulement si aucune ne convient.\n"
        "Pour les champs avec plusieurs éléments, mets un élément par ligne (pas de markdown).\n"
        "Analyse : Dis moi si je dois te fournir plus de detail et Donne moi des suggestions si applicable en utilisant le champ `analyze` au format Markdown."
        "NB: uniquement le champ `analyze` accepte le markdown"
    )
    try:
        client = get_genai_client()
    except (UndefinedValueError, ValueError) as exc:
        raise OfferGenerationError('ai_not_configured', 'Le service IA n’est pas configuré. Vérifiez GENAI_API_KEY côté serveur.', 503) from exc
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_OFFER_MODEL,
            contents=[prompt],
            config=GenerateContentConfigDict(response_schema=OfferInfo, response_mime_type='application/json'),
        )
    except APIError as exc:
        if exc.code == 404:
            raise OfferGenerationError('ai_model_unavailable', 'Le modèle IA est indisponible. Vérifiez GEMINI_OFFER_MODEL côté serveur.', 503) from exc
        reasons = {d.get('reason') for d in (exc.details or {}).get('error', {}).get('details', []) if isinstance(d, dict)}
        if exc.code in (401, 403) or exc.code == 400 and 'API_KEY_INVALID' in reasons:
            raise OfferGenerationError('ai_authentication_failed', 'Le fournisseur IA refuse l’accès. Vérifiez la clé et les autorisations côté serveur.', 503) from exc
        if exc.code == 429:
            raise OfferGenerationError('ai_rate_limited', 'Le quota ou la limite de requêtes IA est atteint. Réessayez ultérieurement.', 429) from exc
        if exc.code and exc.code >= 500:
            raise OfferGenerationError('ai_provider_unavailable', 'Le fournisseur IA est temporairement indisponible.', 503) from exc
        raise OfferGenerationError('ai_request_rejected', 'Le fournisseur IA n’a pas pu traiter la demande.') from exc
    except (TimeoutException, TimeoutError) as exc:
        raise OfferGenerationError('ai_timeout', 'Le fournisseur IA n’a pas répondu dans le délai imparti. Réessayez ultérieurement.', 504) from exc
    except RequestError as exc:
        raise OfferGenerationError('ai_connection_failed', 'Impossible de joindre le fournisseur IA.', 503) from exc
    try:
        parsed = response.parsed
        generated = OfferInfo.model_validate(parsed) if parsed is not None else OfferInfo.model_validate_json(response.text or '')
    except (ValidationError, ValueError, TypeError, AttributeError) as exc:
        raise OfferGenerationError('ai_invalid_response', 'Le fournisseur IA a renvoyé une réponse inexploitable. Réessayez.') from exc
    result = {key: value if value is not None else ([] if key == 'skills' else '')
              for key, value in generated.model_dump().items()}
    if not any(value.strip() if isinstance(value, str) else value for value in result.values()):
        raise OfferGenerationError('ai_invalid_response', 'Le fournisseur IA n’a généré aucun contenu exploitable.')
    return {**result, 'prompt': prompt_description}
