import os
from functools import cache

from google import genai
from pydantic import BaseModel

from challenges.models import Answer


@cache
def get_genai_client():
    return genai.Client(api_key=os.getenv('GENAI_API_KEY'))


class CorrectorResponse(BaseModel):
    id: int
    correct: bool


GEMINI_MODEL = "gemini-1.5-flash"

GENIMI_CONFIG = {
    'response_mime_type': 'application/json',
    'response_schema': list[CorrectorResponse],
}

answer_prompt = """
ID: {id}
Domain: {domain}
Question: {question}
Description: {description}
Answer: {answer}

"""

prompt = """
Check the correctness of all answers and respond with JSON in the following format:
[
    {
        id: int,
        correct: bool,
    }
    ...
]
"""


def make_answer_prompt(answer: Answer):
    return answer_prompt.format(
        id=answer.id,
        domain=answer.question.domain.name,
        question=answer.question.title,
        description=answer.question.description,
        answer=answer.text
    )


def make_final_prompt(answers: list[Answer]):
    output = ""
    for answer in answers:
        output += make_answer_prompt(answer)
    output += prompt
    return output


def split_batches(answers: list[Answer], max_tokens=900000) -> list[list[Answer]]:
    """Découpe les réponses en lots pour ne pas dépasser la limite de tokens"""
    batches = []
    current_batch = []
    current_tokens = 0

    for answer in answers:
        answer_tokens = get_genai_client().models.count_tokens(
            model=GEMINI_MODEL,
            contents=make_answer_prompt(answer),
        ).total_tokens
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
