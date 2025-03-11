import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from challenges.challenge_gen import generate_challenge_for_user
from challenges.corrector import correct_submission
from challenges.models import Challenge, SubmissionAttempt, Submission, Answer
from questions.models import Question


def home_view(request):
    if not request.user.is_authenticated:
        return render(request, 'challenges/home.html')
    context = {
        'latest_challenges': Challenge.objects.filter(submissions__candidate=request.user).prefetch_related(
            'submissions')
    }
    return render(request, 'challenges/home.html', context)


@login_required
def evaluation_results(request, submission_id=None, slug=None, challenge_id=None):
    candidate = request.user
    if not slug or not challenge_id:
        submissions = User.objects.get(id=request.user.id).submissions.prefetch_related('challenge')
        if submissions.count() == 1:
            submission = submissions.first()
            return redirect('result-detail', submission_id=submission.id, slug=submission.challenge.slug,
                            challenge_id=submission.challenge.id)

        context = {
            'submissions': submissions
        }
        return render(request, 'challenges/result_choose.html', context)

    submission = get_object_or_404(Submission, challenge_id=challenge_id, candidate_id=candidate.id, id=submission_id)
    attempt = SubmissionAttempt.objects.get(candidate=candidate, submission=submission)

    answers = []
    for question in submission.challenge.questions.all():
        answer = submission.answers.filter(question=question).first()
        if not answer:
            answer = Answer(submission=submission, question=question, text=None)
        answers.append(answer)

    return render(request, 'challenges/resultat.html', {
        'submission': submission,
        'answers': answers,
        'attempt': attempt,
    })


@transaction.atomic
@login_required
def challenge_evaluation_view(request, slug=None, challenge_id=None):
    if not request.user.has_skill_infos:
        messages.warning(request, 'Veuillez renseigner vos compétences avant de continuer.')
        return redirect('update_profile')
    if not slug or not challenge_id:
        challenges = User.objects.get(id=request.user.id).challenges.exclude(submissions__candidate_id=request.user.id)
        if challenges.count() == 0:
            challenges = Challenge.objects.filter(attempts__candidate=request.user, attempts__ended_at__isnull=True)
            if challenges.count() == 0:
                challenge = generate_challenge_for_user(request.user)
                request.user.challenges.add(challenge)
                challenges = [challenge]
        context = {
            'challenges': challenges
        }
        return render(request, 'challenges/evaluation_choose.html', context)

    challenge = get_object_or_404(Challenge, slug=slug, id=challenge_id)

    attempt, _ = SubmissionAttempt.objects.get_or_create(candidate=request.user, challenge=challenge)
    if attempt.is_finished:
        messages.warning(request, 'Cette évaluation a déjà été terminée.')
        return redirect('result-detail', submission_id=attempt.submission.id, slug=challenge.slug,
                        challenge_id=challenge.id)
    elapsed_time = (timezone.now() - attempt.started_at).total_seconds()
    time_left = max(challenge.duration.total_seconds() - elapsed_time, 0)

    context = {
        'challenge': challenge,
        'open_answer_questions': challenge.questions.filter(question_type=Question.QuestionType.OPEN_ANSWER),
        'choices_questions': challenge.questions.exclude(question_type=Question.QuestionType.OPEN_ANSWER),
        'time_left': math.ceil(time_left)  # Convert seconds to minutes,
    }  # TODO check timer ps: ask to ai
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

    attempt, _ = SubmissionAttempt.objects.get_or_create(candidate=request.user, challenge=challenge)
    attempt.ended_at = timezone.now()
    attempt.submission = submission
    attempt.save()

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
    return redirect(
        'result-detail',
        challenge_id=submission.challenge.id,
        slug=submission.challenge.slug,
        submission_id=submission.id,
    )
