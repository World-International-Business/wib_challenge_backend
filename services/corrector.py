import logging

from django.db import transaction
from django.utils import timezone

from apps.evaluations.models import Submission, SubmissionAttempt, Answer, EvaluationType
from services.utils import get_genai_client, make_personality_prompt, GEMINI_MODEL, PERSONALITY_CONFIG

logger = logging.getLogger(__name__)


def _calculate_scoring_factor(correct_count: int, incorrect_count: int, total_correct_choices: int) -> tuple[
    float, str, bool]:
    """
    Calcule le facteur de scoring et détermine le statut de la réponse

    Args:
        correct_count: Nombre de choix corrects sélectionnés
        incorrect_count: Nombre de choix incorrects sélectionnés
        total_correct_choices: Nombre total de choix corrects possibles

    Returns:
        tuple: (facteur, statut, is_correct)
    """
    if total_correct_choices == 0:
        return 0.0, Answer.Status.INCORRECT, False

    if incorrect_count == 0 and correct_count == total_correct_choices:
        return 1.0, Answer.Status.CORRECT, True
    elif correct_count > 0 and incorrect_count == 0:
        factor = correct_count / total_correct_choices
        return factor, Answer.Status.PARTIAL, True
    elif correct_count > incorrect_count:
        factor = max(correct_count - incorrect_count, 0) / total_correct_choices
        return factor, Answer.Status.PARTIAL, True
    else:
        return 0.0, Answer.Status.INCORRECT, False


@transaction.atomic
def correct_submission(submission: Submission, attempt: SubmissionAttempt, save=True):
    """
    Corrige une soumission en évaluant chaque réponse

    Args :
        submission : L'objet Submission à corriger
        attempt : L'objet SubmissionAttempt associé
        save : Si True, sauvegarde les changements en base de données

    Returns :
        SubmissionAttempt : La tentative mise à jour

    Raises:
        ValueError: Si les données sont incohérentes
        Exception: Si une erreur inattendue survient
    """
    try:
        if not submission or not attempt:
            raise ValueError("Les paramètres submission et attempt sont requis")

        logger.info(f"Début de correction pour submission {submission.id}, attempt {attempt.id}")

        if hasattr(attempt.evaluation,
                   'type') and attempt.evaluation.evaluation_type == EvaluationType.PERSONALITY:
            return correct_personality_submission(submission, attempt)

        answers = attempt.answers.prefetch_related(
            'selected_choices', 'question__choices').all()

        total_score = 0
        answers_to_update = []

        for answer in answers:
            try:
                if not hasattr(answer, 'question') or not answer.question:
                    logger.warning(f"Réponse {answer.id} sans question associée")
                    continue

                weight = getattr(answer.question, 'weight', 0)
                if weight < 0:
                    logger.warning(f"Question {answer.question.id} avec un poids négatif: {weight}")
                    weight = 0

                correct_choices = list(answer.question.choices.filter(is_correct=True))
                selected_choices = list(answer.selected_choices.all())

                if answer.status in [Answer.Status.DISCARDED, Answer.Status.TIMEOUT]:
                    answer.is_correct = False
                    answer.score = 0
                    answers_to_update.append(answer)
                    continue

                if not correct_choices:
                    logger.warning(f"Question {answer.question.id} sans choix correct défini")
                    answer.status = Answer.Status.INCORRECT
                    answer.is_correct = False
                    answer.score = 0
                    answers_to_update.append(answer)
                    continue

                correct_count = sum(1 for choice in selected_choices if choice in correct_choices)
                incorrect_count = len(selected_choices) - correct_count

                factor, status, is_correct = _calculate_scoring_factor(
                    correct_count, incorrect_count, len(correct_choices)
                )

                answer.status = status
                answer.is_correct = is_correct
                answer.score = int(weight * factor)
                total_score += answer.score
                logger.info(
                    f"Réponse {answer.id} évaluée: status={status}, is_correct={is_correct}, score={answer.score}")
                answers_to_update.append(answer)

            except Exception as e:
                logger.error(f"Erreur lors de la correction de la réponse {answer.id}: {str(e)}")
                answer.status = Answer.Status.INCORRECT
                answer.is_correct = False
                answer.score = 0
                answers_to_update.append(answer)

        if save and answers_to_update:
            attempt.answers.model.objects.bulk_update(
                answers_to_update,
                ['status', 'is_correct', 'score']
            )

            submission.score = total_score
            submission.save()

            attempt.ended_at = timezone.now()
            attempt.corrected = True
            attempt.save()

        logger.info(f"Correction terminée. Score total: {total_score}")
        return attempt

    except Exception as e:
        logger.error(f"Erreur lors de la correction de la soumission {submission.id}: {str(e)}")
        raise


@transaction.atomic
def correct_personality_submission(submission: Submission, attempt: SubmissionAttempt, save=True):
    client = get_genai_client()

    answers = attempt.answers.prefetch_related(
        'selected_choices', 'question__choices').all()

    if len(answers) == 0:
        return None

    prompt = make_personality_prompt(list(answers))

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt],
        config=PERSONALITY_CONFIG,
    )

    submission.personality_detail = response.text
    attempt.corrected = True
    if save and submission.personality_detail is not None:
        submission.save()
        answers.update(status=Answer.Status.CORRECT)
        attempt.save()

    return attempt
