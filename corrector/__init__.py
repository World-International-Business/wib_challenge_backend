from django.db import transaction
from django.utils import timezone
import logging

from evaluations.models import Submission, SubmissionAttempt, Answer
from organizations.models import OrgSubmission, OrgSubmissionAttempt

logger = logging.getLogger(__name__)


def _calculate_scoring_factor(correct_count: int, incorrect_count: int, total_correct_choices: int) -> tuple[float, str, bool]:
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
        # Toutes les bonnes réponses sélectionnées, aucune mauvaise
        return 1.0, Answer.Status.CORRECT, True
    elif correct_count > 0 and incorrect_count == 0:
        # Quelques bonnes réponses, mais pas toutes, et aucune mauvaise
        factor = correct_count / total_correct_choices
        return factor, Answer.Status.PARTIAL, True
    elif correct_count > incorrect_count:
        # Plus de bonnes réponses que de mauvaises, mais pas parfait
        factor = max(correct_count - incorrect_count, 0) / total_correct_choices
        return factor, Answer.Status.PARTIAL, True
    else:
        # Trop de mauvaises réponses ou aucune bonne
        return 0.0, Answer.Status.INCORRECT, False


@transaction.atomic
def correct_submission(submission: Submission | OrgSubmission, attempt: SubmissionAttempt | OrgSubmissionAttempt,
                       save=True):
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
        # Validation des paramètres d'entrée
        if not submission or not attempt:
            raise ValueError("Les paramètres submission et attempt sont requis")
            
        logger.info(f"Début de correction pour submission {submission.id}, attempt {attempt.id}")
        
        # Préchargement optimisé des données
        answers = attempt.answers.prefetch_related(
            'selected_choices', 'question__choices').all()

        total_score = 0
        answers_to_update = []

        for answer in answers:
            try:
                # Validation de la question
                if not hasattr(answer, 'question') or not answer.question:
                    logger.warning(f"Réponse {answer.id} sans question associée")
                    continue
                    
                # Validation du poids de la question
                weight = getattr(answer.question, 'weight', 0)
                if weight < 0:
                    logger.warning(f"Question {answer.question.id} avec un poids négatif: {weight}")
                    weight = 0

                correct_choices = list(answer.question.choices.filter(is_correct=True))
                selected_choices = list(answer.selected_choices.all())

                # Traitement des réponses abandonnées ou en timeout
                if answer.status in [Answer.Status.DISCARDED, Answer.Status.TIMEOUT]:
                    answer.is_correct = False
                    answer.score = 0
                    answers_to_update.append(answer)
                    continue

                # Validation des choix disponibles
                if not correct_choices:
                    logger.warning(f"Question {answer.question.id} sans choix correct défini")
                    answer.status = Answer.Status.INCORRECT
                    answer.is_correct = False
                    answer.score = 0
                    answers_to_update.append(answer)
                    continue

                # Compter les réponses correctes et incorrectes
                correct_count = sum(1 for choice in selected_choices if choice in correct_choices)
                incorrect_count = len(selected_choices) - correct_count

                # Calculer le facteur de scoring
                factor, status, is_correct = _calculate_scoring_factor(
                    correct_count, incorrect_count, len(correct_choices)
                )

                # Mettre à jour les propriétés de la réponse
                answer.status = status
                answer.is_correct = is_correct
                answer.score = int(weight * factor)
                total_score += answer.score
                
                answers_to_update.append(answer)
                
            except Exception as e:
                logger.error(f"Erreur lors de la correction de la réponse {answer.id}: {str(e)}")
                # En cas d'erreur, marquer la réponse comme incorrecte
                answer.status = Answer.Status.INCORRECT
                answer.is_correct = False
                answer.score = 0
                answers_to_update.append(answer)

        if save and answers_to_update:
            # Optimisation: mise à jour en lot
            Answer.objects.bulk_update(
                answers_to_update, 
                ['status', 'is_correct', 'score']
            )

            submission.score = total_score
            submission.save()

            attempt.ended_at = timezone.now()
            attempt.save()
            
        logger.info(f"Correction terminée. Score total: {total_score}")
        return attempt
        
    except Exception as e:
        logger.error(f"Erreur lors de la correction de la soumission {submission.id}: {str(e)}")
        raise
