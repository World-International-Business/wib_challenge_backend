from dataclasses import dataclass

from django.db.models import QuerySet, Sum

from apps.core.models import Technology
from apps.evaluations.models import Answer, SubmissionAttempt


@dataclass
class AnswerStats:
    correct: int = 0
    partial: int = 0
    timeout: int = 0
    discarded: int = 0
    incorrect: int = 0


@dataclass
class TechnologyStats:
    technology: Technology
    score: float
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    partial_answers: int
    timeout_answers: int
    discarded_answers: int


def split_answers(answers: QuerySet[Answer]) -> AnswerStats:
    if not answers.exists():
        return AnswerStats()
    stats = AnswerStats()
    stats.correct = answers.filter(status=Answer.Status.CORRECT).count()
    stats.partial = answers.filter(status=Answer.Status.PARTIAL).count()
    stats.timeout = answers.filter(status=Answer.Status.TIMEOUT).count()
    stats.discarded = answers.filter(status=Answer.Status.DISCARDED).count()
    stats.incorrect = answers.filter(status=Answer.Status.INCORRECT).count()
    return stats


def get_evaluation_tech_stats(attempt: SubmissionAttempt) -> list[TechnologyStats]:
    technologies = Technology.objects.filter(questions__evaluations=attempt.evaluation).distinct()

    stats = []
    for tech in technologies:
        tech_questions = tech.questions.filter(evaluations=attempt.evaluation)
        answers = attempt.answers.filter(question__in=tech_questions)

        total_questions = tech_questions.count()
        stat = split_answers(answers)

        score = answers.aggregate(total_score=Sum('score'))['total_score'] or 0.0

        stats.append(TechnologyStats(
            technology=tech,
            score=round(score, 2),
            total_questions=total_questions,
            correct_answers=stat.correct,
            incorrect_answers=stat.incorrect,
            partial_answers=stat.partial,
            timeout_answers=stat.timeout,
            discarded_answers=stat.discarded
        ))
    return stats
