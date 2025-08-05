from functools import cache

from decouple import config
from google import genai

from organizations.models import OrgAnswer as Answer


@cache
def get_genai_client():
    return genai.Client(api_key=config('GENAI_API_KEY'))


GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MODEL_LITE = "gemini-2.0-flash-lite"

PERSONALITY_CONFIG = {
    'temperature': 0.7,
    'max_output_tokens': 2048,
}

_personality_answer_prompt = """
Question: {question}
Description: {description}
{extras}
Réponse: {answer}
"""

_personality_prompt = """
Tu es un psychologue expert en analyse comportementale. Analyse les réponses du candidat à ce test de personnalité.
Pour le Poste de {domain} dans une startup IT

Voici le test de personnalité:

{content}

Sur la base de ces réponses, fournis une analyse complète de la personnalité du candidat en structurant automatiquement ton analyse selon les thématiques qui ressortent des questions posées. 

Organise ta réponse avec:
- Introduction: Présentation générale du profil
- Développement: Analyse détaillée par thématiques identifiées (traits de personnalité, compétences comportementales, aptitudes professionnelles, etc.) en te basant sur les domaines couverts par les questions
- Conclusion: Synthèse et adéquation au poste

Identifie et traite automatiquement les axes d'analyse pertinents selon les questions du test. Reste objectif et factuel dans ton analyse. Limite ta réponse à environ 600 mots.
"""


def make_personality_answer_prompt(answer: Answer):
    answer_text = answer.text if hasattr(answer, 'text') else ''
    extras = ''
    if not answer_text and answer.selected_choices.exists():
        answer_text = ", ".join([choice.text for choice in answer.selected_choices.all()])
        extras = ', '.join([choice.text for choice in answer.question.choices.all()])

    return _personality_answer_prompt.format(
        question=answer.question.text,  # answer.question.title,
        description='',  # answer.question.description,
        answer=answer_text,
        extras=f'Choix proposés: {extras}'
    )


def make_personality_prompt(answers: list[Answer]):
    answers_text = ""
    for answer in answers:
        answers_text += make_personality_answer_prompt(answer)

    return _personality_prompt.format(
        content=answers_text,
        domain=answers[0].question.evaluation.profession.title
    )
