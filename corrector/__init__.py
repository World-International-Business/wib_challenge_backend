from django.db import transaction
from django.utils import timezone

from evaluations.models import Submission, SubmissionAttempt, Answer
from organizations.models import OrgSubmission, OrgSubmissionAttempt


@transaction.atomic
def correct_submission(submission: Submission | OrgSubmission, attempt: SubmissionAttempt | OrgSubmissionAttempt,
                       save=True):
    """
    Corrige une soumission en évaluant chaque réponse
    
    Args :
        submission : L'objet Submission à corriger
        attempt : L'objet SubmissionAttempt associé
        save : Si True, sauvegarde les changements en base de données
        
    Returns :
        SubmissionAttempt : La tentative mise à jour
    """
    # Préchargement optimisé des données
    answers = attempt.answers.prefetch_related(
        'selected_choices', 'question__choices').all()

    total_score = 0

    for answer in answers:
        correct_choices = list(answer.question.choices.filter(is_correct=True))
        selected_choices = list(answer.selected_choices.all())

        # Traitement des réponses abandonnées ou en timeout
        if answer.status in [Answer.Status.DISCARDED, Answer.Status.TIMEOUT]:
            answer.is_correct = False
            answer.score = 0
            continue

        # Compter les réponses correctes et incorrectes
        correct_count = sum(1 for choice in selected_choices if choice in correct_choices)
        incorrect_count = len(selected_choices) - correct_count

        # Déterminer l'état de la réponse
        if incorrect_count == 0 and correct_count == len(correct_choices):
            # Toutes les bonnes réponses sélectionnées, aucune mauvaise
            answer.status = Answer.Status.CORRECT
            answer.is_correct = True
            factor = 1.0
        elif correct_count > 0 and incorrect_count == 0:
            # Quelques bonnes réponses, mais pas toutes, et aucune mauvaise
            answer.status = Answer.Status.PARTIAL
            answer.is_correct = True
            factor = correct_count / len(correct_choices)
        elif correct_count > incorrect_count:
            # Plus de bonnes réponses que de mauvaises, mais pas parfait
            answer.status = Answer.Status.PARTIAL
            answer.is_correct = True
            factor = max(correct_count - incorrect_count, 0) / len(correct_choices)
        else:
            # Trop de mauvaises réponses ou aucune bonne
            answer.status = Answer.Status.INCORRECT
            answer.is_correct = False
            factor = 0

        # Calculer le score
        weight = answer.question.weight
        answer.score = int(weight * factor)
        total_score += answer.score

        if save:
            answer.save()

    if save:
        submission.score = total_score
        submission.save()

        attempt.ended_at = timezone.now()
        attempt.save()

    return attempt
