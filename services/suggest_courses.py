from functools import cache

from apps.evaluations.models import SubmissionAttempt
from apps.evaluations.utils.stats import get_evaluation_tech_stats, TechnologyStats
from apps.learning.models import Course
import logging

logger = logging.getLogger(__name__)


@cache
def suggest_courses_from_attempt(attempt: SubmissionAttempt):
    """
    Analyse une soumission pour identifier les technologies "faible" pour l'utilisateur.

    Une technologie est considérée comme fragile si le score de performance, calculé
    en fonction de la correctitude des réponses de l'utilisateur, est inférieur à un seuil
    donné.
    """
    stats = get_evaluation_tech_stats(attempt)

    # Une technologie est considérée comme faible si le score de performance est inférieur à ce seuil.
    WEAK_TECH_THRESHOLD = 0.5

    def is_weak_tech(stat: TechnologyStats) -> bool:
        """
        Calcule un score de performance et détermine si la technologie est un point faible.

        Le score est pondéré : les réponses correctes valent 1 point, les réponses partielles 0.5 points,
        et toutes les autres réponses (incorrectes, délai d'expiration, ignorées) valent 0 points.
        Le score total est ensuite normalisé par le nombre de questions.
        """
        total_questions = stat.total_questions
        if total_questions == 0:
            return False

        # Calcule un score simple et intuitif basé sur les performances.
        # Correct = 1.0, Partial = 0.5,Autres = 0.0
        performance_score = (
                                    (stat.correct_answers * 1.0) + (stat.partial_answers * 0.5)
                            ) / total_questions

        if performance_score < WEAK_TECH_THRESHOLD:
            logger.info(f"Technology '{stat.technology.name}' is weak with performance score: {performance_score:.2f}")

        return performance_score < WEAK_TECH_THRESHOLD

    logger.info(f"Analyzing submission attempt {attempt.id} for weak technologies.")
    weak_techs = [stat.technology.id for stat in stats if is_weak_tech(stat)]
    logger.info(f"Identified weak technologies (IDs): {weak_techs}")

    courses = Course.objects.filter(skills__in=weak_techs).distinct().order_by('-updated_at', '-created_at')
    logger.info(f"Found {len(courses)} suggested courses for weak technologies.")

    return courses
