import os
from functools import cache

from google import genai
from pydantic import BaseModel

from challenges.models import Answer, PersonalityAnswer


@cache
def get_genai_client():
    return genai.Client(api_key=os.getenv('GENAI_API_KEY'))


class CorrectorResponse(BaseModel):
    id: int
    correct: bool


GEMINI_MODEL = "gemini-3.6-flash"

GENIMI_CONFIG = {
    'response_mime_type': 'application/json',
    'response_schema': list[CorrectorResponse],
}

# Configuration pour l'analyse de personnalité
PERSONALITY_CONFIG = {
    'temperature': 0.7,
    'max_output_tokens': 2048,
}

_answer_prompt = """
ID: {id}
Domain: {domain}
Question: {question}
Description: {description}
Answer: {answer}

"""

_prompt = """
Check the correctness of all answers and respond with JSON in the following format:
[
    {
        id: int,
        correct: bool,
    }
    ...
]
"""

_personality_answer_prompt = """
Question: {question}
Description: {description}
{extras}
Réponse: {answer}
"""

_personality_prompt = """
Tu es un psychologue expert en analyse comportementale. Analyse les réponses du candidat à ce test de personnalité.
Pour le Poste de {domain} dans une startup IT

Voici ses réponses:

{answers}

Sur la base de ces réponses, fournis une analyse complète de la personnalité du candidat, comprenant:
Introduction
Traits de personnalité dominants
Forces et qualités
Points d'amélioration potentiels
Style de travail et de communication
Compatibilité avec différents environnements professionnels
Conclusion

Reste objectif et factuel dans ton analyse. Limite ta réponse à environ 600 mots.
"""


def make_answer_prompt(answer: Answer):
    return _answer_prompt.format(
        id=answer.id,
        domain=answer.question.category.name,
        question=answer.question.title,
        description=answer.question.description,
        answer=answer.text
    )


def make_final_prompt(answers: list[Answer]):
    output = ""
    for answer in answers:
        output += make_answer_prompt(answer)
    output += _prompt
    return output


def make_personality_answer_prompt(answer: PersonalityAnswer):
    answer_text = answer.text
    extras = ''
    if not answer_text and answer.selected_choices.exists():
        answer_text = ", ".join([choice.text for choice in answer.selected_choices.all()])
        extras = ', '.join([choice.text for choice in answer.question.choices.all()])

    return _personality_answer_prompt.format(
        question=answer.question.title,
        description=answer.question.description,
        answer=answer_text,
        extras=f'Choix proposés: {extras}'
    )


def make_personality_prompt(answers: list[PersonalityAnswer]):
    answers_text = ""
    for answer in answers:
        answers_text += make_personality_answer_prompt(answer)

    return _personality_prompt.format(
        answers=answers_text,
        domain=answers[0].question.category.domain.name
    )


def estimate_tokens(text: str) -> int:
    """Estimation rapide : environ 1 token pour 4 caractères."""
    return max(1, len(text) // 4)


def split_batches(answers: list[Answer], max_tokens=900000) -> list[list[Answer]]:
    """Découpe les réponses en lots pour ne pas dépasser la limite de tokens"""
    batches = []
    current_batch = []
    current_tokens = 0

    for answer in answers:
        answer_tokens = estimate_tokens(make_answer_prompt(answer))
        if current_tokens + answer_tokens > max_tokens:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
        current_batch.append(answer)
        current_tokens += answer_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def split_choices_and_open_answers(answers: list[Answer]) -> tuple[list[Answer], list[Answer]]:
    choices = []
    open_answers = []
    for answer in answers:
        if answer.question.is_open_answer:
            open_answers.append(answer)
        else:
            choices.append(answer)
    return choices, open_answers
