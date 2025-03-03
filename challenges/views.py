from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from accounts.models import User
from challenges.corrector import correct_submission
from .models import Challenge, Question
from .models import Submission, Answer


def home_view(request):
    # Récupérer les 3 derniers challenges
    return render(request, 'challenges/home.html')


@login_required
def evaluation_results(request, submission_id=None, slug=None, challenge_id=None):
    candidate = request.user
    if not slug or not challenge_id:
        submissions = User.objects.get(id=request.user.id).submissions.prefetch_related('challenge')
        if submissions.count() == 1:
            submission = submissions.first()
            return redirect('resultat-detail', submission_id=submission.id, slug=submission.challenge.slug,
                            challenge_id=submission.challenge.id)

        context = {
            'submissions': submissions
        }
        return render(request, 'challenges/result_choose.html', context)

    submission = get_object_or_404(Submission, challenge_id=challenge_id, candidate_id=candidate.id, id=submission_id)

    return render(request, 'challenges/resultat.html', {'submission': submission, })


@login_required
def challenge_evaluation_view(request, slug=None, challenge_id=None):
    if not slug or not challenge_id:
        challenges = User.objects.get(id=request.user.id).challenges.exclude(submissions__candidate_id=request.user.id)
        if challenges.count() == 1:
            challenge = challenges.first()
            return redirect('challenge_evaluation_detail', slug=challenge.slug, challenge_id=challenge.id)
        context = {
            'challenges': challenges
        }
        return render(request, 'challenges/evaluation_choose.html', context)

    challenge = get_object_or_404(Challenge, slug=slug, id=challenge_id)

    context = {
        'challenge': challenge,
        'open_answer_questions': challenge.questions.filter(question_type=Question.QuestionType.OPEN_ANSWER),
        'choices_questions': challenge.questions.exclude(question_type=Question.QuestionType.OPEN_ANSWER),
    }
    return render(request, 'challenges/evaluation.html', context)


@login_required
@transaction.atomic
def submit_evaluation_view(request):
    if request.method != 'POST':
        return redirect('home')

    answers = []

    challenge = get_object_or_404(Challenge, id=request.POST.get('challenge_id'))
    submission = Submission.objects.create(
        candidate=request.user,
        challenge=challenge
    )
    for key in request.POST:
        if key.startswith('answer_'):
            question_id = int(key.split('_')[-1])
            values = list(filter(lambda x: bool(x), request.POST.getlist(key, [])))
            if not values:
                continue
            question = get_object_or_404(Question, id=question_id)
            if question.question_type == Question.QuestionType.OPEN_ANSWER:
                answers.append(
                    Answer.objects.create(
                        submission=submission,
                        question=question,
                        text=values[0]
                    )
                )
            else:
                answer = Answer.objects.create(
                    submission=submission,
                    question=question,
                )
                answer.selected_choices.set(values)
                answers.append(answer)
    submission.save()
    correct_submission(submission)
    return redirect('home')
