from google.genai.types import GenerateContentConfigDict
from pydantic import BaseModel

from services.utils import get_genai_client, GEMINI_MODEL_LITE


class OfferInfo(BaseModel):
    title: str | None = None
    description: str | None = None
    responsibilities: str | None = None
    requirements: str | None = None
    benefits: str | None = None
    analyze: str | None = None


def generate_offer(prompt_description: str, data: dict[str, str]):
    print(data)
    offer = OfferInfo(**data)
    prompt = (
        "En tant qu'expert en Ressources Humaines\n"
        "Génère une offre d'emploi détaillée à partir des informations suivantes :\n"
        f"Titre : {offer.title or 'Non spécifié'}\n"
        f"Contexte : {prompt_description}\n"
        f"Description : {offer.description or 'Non spécifié'}\n"
        f"Responsabilités : {offer.responsibilities or 'Non spécifié'}\n"
        f"Exigences : {offer.requirements or 'Non spécifié'}\n"
        f"Avantages : {offer.benefits or 'Non spécifié'}\n"
        "Structure l'offre de façon professionnelle et attractive.\n"
        "Analyse : Dis moi si je dois te fournir plus de detail et Donne moi des suggestions si applicable en utilisant le champ `analyze` au format Markdown."
        "NB: uniquement le champ `analyze` accepte le markdown"
    )
    client = get_genai_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL_LITE,
        contents=[prompt],
        config=GenerateContentConfigDict(
            response_schema=OfferInfo,
            response_mime_type='application/json'
        )
    )
    return {**response.parsed.model_dump(), "prompt": prompt_description}
