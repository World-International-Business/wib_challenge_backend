import json
import os
from functools import cache

from google import genai
from pydantic import BaseModel

from challenges.models import Answer, Submission


@cache
def get_genai_client():
    return genai.Client(api_key=os.getenv('GENAI_API_KEY'))


class CorrectorResponse(BaseModel):
    correct: bool


def correct_answer(answer: Answer):
    prompt = f"""
    Domain: {answer.question.domain.name}
    Question: {answer.question.title}
    Description: {answer.question.description}
    
    Answer: {answer.text}
     
    Check the correctness of the answer, and respond with JSON in the following format:
    {{
        "correct": true/false,
    }}
    
    respond in french language
    """

    client = get_genai_client()

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt],
        config={
            'response_mime_type': 'application/json',
            'response_schema': CorrectorResponse,
        },
    )
    data = json.loads(response.text)
    return CorrectorResponse(**data)


def correct_answer_choice(answer: Answer):
    if answer.question.is_unique_choice:
        correct_choice = answer.question.choices.get(is_correct=True)
        correct = answer.selected_choices.first() == correct_choice,
        return CorrectorResponse(
            correct=bool(correct),
        )
    else:
        correct_choices = answer.question.choices.filter(is_correct=True)
        selected_choices = answer.selected_choices.all()
        correct_count = correct_choices.filter(id__in=selected_choices).count()
        correct = correct_count != 0
        return CorrectorResponse(
            correct=correct,
        )


def correct_submission(submission: Submission):
    answers = submission.answers.all()
    for answer in answers:
        if answer.corrected:
            continue
        if answer.question.question_type == answer.question.QuestionType.OPEN_ANSWER:
            response = correct_answer(answer)
        else:
            response = correct_answer_choice(answer)
        answer.is_correct = response.correct
        answer.save()
    if len(answers) == 0:
        submission.result = 0
    else:
        submission.result = sum(answer.average_score for answer in answers) / submission.challenge.questions.count()
    submission.save()
    return answers
