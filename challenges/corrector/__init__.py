import json
from datetime import date

from django.db import transaction

from challenges.models import Submission, APIUsage, PersonalityChallenge, Answer
from challenges.corrector.utils import get_genai_client, CorrectorResponse, GEMINI_MODEL, GENIMI_CONFIG, PERSONALITY_CONFIG, make_final_prompt, make_personality_prompt, split_batches, split_choices_and_open_answers


def correct_answers(answers: list[Answer]):
    client = get_genai_client()
    prompt = make_final_prompt(answers)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt],
        config=GENIMI_CONFIG,
    )
    text = response.text.strip()
    if not text:
        raise ValueError('Réponse vide de Gemini')

    # Extraire le JSON si Gemini l'a enveloppé dans du markdown
    if text.startswith('```'):
        lines = text.splitlines()
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].startswith('```'):
            lines = lines[:-1]
        text = '\n'.join(lines).strip()

    datas = json.loads(text)
    if not isinstance(datas, list):
        raise ValueError('Format de réponse invalide')
    return [CorrectorResponse(**data) for data in datas]


def correct_answer_choice(answer: Answer):
    if answer.question.is_unique_choice:
        correct_choice = answer.question.choices.filter(is_correct=True).first()
        selected = answer.selected_choices.first()
        correct = selected is not None and correct_choice is not None and selected.id == correct_choice.id
        return CorrectorResponse(
            id=answer.id,
            correct=correct,
        )
    else:
        correct_choices = answer.question.choices.filter(is_correct=True)
        selected_choices = answer.selected_choices.all()
        correct_count = correct_choices.filter(id__in=selected_choices).count()
        correct = correct_count != 0
        return CorrectorResponse(
            id=answer.id,
            correct=correct,
        )


def correct_submission(submission: Submission):
    try:
        client = get_genai_client()
        answers = list(submission.answers.all())
        choices_answers, open_answers = split_choices_and_open_answers(answers)

        for answer in choices_answers:
            response = correct_answer_choice(answer)
            answer.is_correct = response.correct
            answer.save()

        if open_answers:
            usage, _ = APIUsage.objects.get_or_create(date=date.today())
            try:
                max_tokens = client.models.get(
                    model=f"models/{GEMINI_MODEL}").input_token_limit - 50000
            except Exception:
                max_tokens = 800000
            batches = split_batches(open_answers, max_tokens)

            for batch in batches:
                try:
                    response = correct_answers(batch)
                    for answer, resp in zip(batch, response):
                        answer.is_correct = resp.correct
                        answer.save()
                except Exception:
                    for answer in batch:
                        answer.is_correct = None
                        answer.save()
            usage.count += 1
            usage.save()

        if len(answers) == 0:
            submission.result = 0
        else:
            submission.result = sum(
                answer.average_score for answer in answers) / submission.challenge.questions.count()
        submission.status = Submission.CorrectionStatus.CORRECTED
    except Exception:
        submission.status = Submission.CorrectionStatus.PENDING
    submission.save()
    return answers


def correct_personality_challenge(challenge: PersonalityChallenge):
    try:
        client = get_genai_client()
        answers = list(challenge.answers.all())

        if len(answers) == 0:
            return None
        usage, _ = APIUsage.objects.get_or_create(date=date.today())

        prompt = make_personality_prompt(answers)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt],
            config=PERSONALITY_CONFIG,
        )

        challenge.personality_detail = response.text
        challenge.corrected = True
        challenge.save()

        usage.count += 1
        usage.save()
    except Exception:
        challenge.corrected = False
        challenge.save()

    return challenge
