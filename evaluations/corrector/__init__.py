from evaluations.models import Submission, SubmissionAttempt, Answer
from questions.models import Question


def correct_submission(submission: Submission, save=True):
    """
    Correct the submission
    """
    attempt = submission.attempt
    answers = attempt.answers.prefetch_related('selected_choices', 'question__choices').all()
    for answer in answers:
        correct_choices = answer.question.choices.filter(is_correct=True)
        selected_choices = answer.selected_choices.all()
        correct_count, incorrect_count = 0, 0
        for choice in selected_choices:
            if choice in correct_choices:
                correct_count += 1
            else:
                incorrect_count += 1

        answer.is_correct = correct_count != 0
        if answer.status == Answer.Status.DISCARDED or answer.status == Answer.Status.TIMEOUT:
            answer.is_correct = False
        else:
            if incorrect_count == 0:
                answer.is_correct = True
                answer.status = Answer.Status.CORRECT
            elif correct_count == 0:
                answer.is_correct = False
                answer.status = Answer.Status.INCORRECT
            elif correct_count > incorrect_count:
                answer.is_correct = True
                answer.status = Answer.Status.PARTIAL
            else:
                answer.is_correct = False
                answer.status = Answer.Status.INCORRECT
        factor = 1 if correct_count == len(
            correct_choices) else 0 if correct_count == 0 else correct_count - incorrect_count
        answer.score = Question.Difficulty(answer.question.difficulty).weight * factor

    if save:
        submission.save()
        attempt.save()
