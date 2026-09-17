import json
import logging
from datetime import date

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.urls import reverse
from django.template.loader import render_to_string

from challenges.models import Submission, APIUsage, PersonalityChallenge, Answer
from challenges.corrector.utils import get_genai_client, CorrectorResponse, GEMINI_MODEL, GENIMI_CONFIG, PERSONALITY_CONFIG, make_final_prompt, make_personality_prompt, split_batches, split_choices_and_open_answers

logger = logging.getLogger(__name__)


def _public_url(path):
    base_url = getattr(settings, 'PUBLIC_SITE_URL', '').rstrip('/')
    if base_url:
        return f'{base_url}{path}'
    if settings.DEBUG:
        return f'http://127.0.0.1:8000{path}'
    raise RuntimeError('PUBLIC_SITE_URL doit être configurée en production')


def _notify_candidate_results(challenge, result_url, result_type):
    candidate = challenge.candidate
    if not candidate.email:
        return

    if result_type == 'personality':
        subject = 'Votre analyse de personnalité est disponible'
        heading = 'Votre analyse de personnalité est disponible'
        message = 'Votre test de personnalité a été analysé. Vous pouvez consulter votre synthèse depuis votre espace candidat.'
    else:
        subject = 'Les résultats de votre évaluation sont disponibles'
        heading = 'Les résultats de votre évaluation sont disponibles'
        message = 'La correction de votre évaluation est terminée. Consultez votre score et le détail de vos résultats depuis votre espace candidat.'

    email = EmailMultiAlternatives(
        subject,
        f'Bonjour {candidate.first_name},\n\n{message}\n\nConsulter : {result_url}',
        settings.DEFAULT_FROM_EMAIL,
        [candidate.email],
    )
    email.attach_alternative(
        render_to_string('challenges/candidate_results_email.html', {
            'first_name': candidate.first_name,
            'heading': heading,
            'message': message,
            'result_url': result_url,
        }),
        'text/html',
    )
    email.send(fail_silently=False)


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
                    responses = correct_answers(batch)
                    expected_ids = {answer.id for answer in batch}
                    response_by_id = {}
                    for response in responses:
                        if response.id not in expected_ids or response.id in response_by_id:
                            raise ValueError('Réponse Gemini avec un identifiant inattendu ou dupliqué')
                        response_by_id[response.id] = response
                    if set(response_by_id) != expected_ids:
                        raise ValueError('Réponse Gemini incomplète pour le lot de correction')

                    for answer in batch:
                        answer.is_correct = response_by_id[answer.id].correct
                        answer.save()
                except Exception:
                    for answer in batch:
                        answer.is_correct = None
                        answer.save()
                    raise
            usage.count += 1
            usage.save()

        if len(answers) == 0:
            submission.result = 0
        else:
            submission.result = sum(
                answer.average_score for answer in answers) / submission.challenge.questions.count()
        submission.status = Submission.CorrectionStatus.CORRECTED
    except Exception:
        logger.exception('Erreur lors de la correction de la soumission %s', submission.pk)
        submission.status = Submission.CorrectionStatus.PENDING
    submission.save()
    if submission.status == Submission.CorrectionStatus.CORRECTED:
        result_path = reverse('result-detail', kwargs={
            'submission_id': submission.id,
            'slug': submission.challenge.slug,
            'challenge_id': submission.challenge_id,
        })
        try:
            _notify_candidate_results(
                submission,
                _public_url(result_path),
                'technical',
            )
        except Exception:
            logger.exception('Erreur lors de la notification des résultats %s', submission.pk)
    return answers


def correct_personality_challenge(challenge: PersonalityChallenge):
    try:
        client = get_genai_client()
        answers = list(
            challenge.answers.select_related('question__category__domain').prefetch_related(
                'selected_choices', 'question__choices'
            ).order_by('id')
        )

        if len(answers) == 0:
            challenge.corrected = False
            challenge.personality_detail = ''
            challenge.save(update_fields=['corrected', 'personality_detail'])
            return None
        usage, _ = APIUsage.objects.get_or_create(date=date.today())

        prompt = make_personality_prompt(answers)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt],
            config=PERSONALITY_CONFIG,
        )

        analysis = (response.text or '').strip()
        if not analysis:
            raise ValueError('Réponse vide de Gemini pour l analyse de personnalité')

        challenge.personality_detail = analysis
        challenge.corrected = True
        challenge.save(update_fields=['personality_detail', 'corrected'])

        result_path = reverse('personality_details', kwargs={'user_id': challenge.candidate_id})
        try:
            _notify_candidate_results(
                challenge,
                _public_url(result_path),
                'personality',
            )
        except Exception:
            logger.exception('Erreur lors de la notification de personnalité %s', challenge.pk)

        usage.count += 1
        usage.save()
    except Exception:
        logger.exception('Erreur lors de la correction de personnalité %s', challenge.pk)
        challenge.corrected = False
        challenge.personality_detail = ''
        challenge.save(update_fields=['corrected', 'personality_detail'])

    return challenge
