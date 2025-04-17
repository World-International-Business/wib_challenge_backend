import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import mail_managers
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
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
    if request.user.is_staff and request.GET.get('user_id', None):
        candidate = get_object_or_404(User, pk=request.GET.get('user_id'))
    if not slug or not challenge_id:
        if request.user.is_staff and candidate == request.user:
            submissions = Submission.objects.all()
        else:
            submissions = User.objects.get(id=candidate.id).submissions.all()
        submissions = submissions.prefetch_related('challenge').select_related('candidate').all()

        if submissions.count() == 1:
            submission = submissions.first()
            return redirect('result-detail', submission_id=submission.id, slug=submission.challenge.slug,
                            challenge_id=submission.challenge.id)

        context = {
            'submissions': submissions,
            'add_id': request.user.is_staff,
        }
        return render(request, 'challenges/result_choose.html', context)

    submission = get_object_or_404(
        Submission.objects.prefetch_related('challenge__questions', 'challenge__questions__choices',
                                            'answers', 'challenge__attempts', 'answers__selected_choices',
                                            'answers__question', 'challenge__domain'
                                            ).select_related('candidate'),
        challenge_id=challenge_id, candidate_id=candidate.id, id=submission_id)
    attempt = submission.attempt

    answers = []

    for question in submission.challenge.questions.all():
        answer = submission.answers.filter(question=question).first()
        if not answer:
            answer = Answer(submission=submission, question=question, text=None)
        answers.append(answer)

    # Calcul des statistiques
    total_questions = submission.challenge.questions.count()
    answer_count = submission.answers.count()
    correct_count = submission.answers.filter(is_correct=True).count()
    wrong_count = submission.answers.filter(is_correct=False).count()
    unanswered_count = total_questions - answer_count
    partial_correct_count = 0
    for answer in answers:
        if 0 < answer.average_score < 1:
            partial_correct_count += 1

    # Calcul des pourcentages pour les statistiques partielles
    correct_percent = (correct_count / total_questions * 100) if total_questions > 0 else 0
    wrong_percent = (wrong_count / total_questions * 100) if total_questions > 0 else 0
    unanswered_percent = (unanswered_count / total_questions * 100) if total_questions > 0 else 0
    partial_correct_percent = (partial_correct_count / total_questions * 100) if total_questions > 0 else 0

    top_submissions = Submission.objects.filter(
        challenge__domain=submission.challenge.domain
    ).select_related('candidate').order_by('-result')[:10]

    # Structure pour stocker les données des candidats
    candidates = []
    user_in_top = False

    for i, sub in enumerate(top_submissions):
        candidates.append({
            'rank': i + 1,
            'self': sub.candidate.id == candidate.id,
            'first_name': sub.candidate.first_name,
            'last_name': sub.candidate.last_name,
            'score': sub.result_percent,
        })
        if sub.candidate.id == candidate.id:
            user_in_top = True

    if not user_in_top:
        candidates.append(None)
        user_rank = Submission.objects.filter(
            challenge__domain=submission.challenge.domain,
            result__gt=submission.result
        ).count() + 1
        candidates.append({
            'rank': user_rank,
            'first_name': candidate.first_name,
            'self': True,
            'last_name': candidate.last_name,
            'score': submission.result_percent,
        })

    return render(request, 'challenges/resultat.html', {
        'submission': submission,
        'answers': answers,
        'attempt': attempt,
        'answer_count': answer_count,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'unanswered_count': unanswered_count,
        'correct_percent': correct_percent,
        'wrong_percent': wrong_percent,
        'unanswered_percent': unanswered_percent,
        'partial_correct_count': partial_correct_count,
        'partial_correct_percent': partial_correct_percent,
        'total_questions': total_questions,
        'candidates': candidates,
    })


@transaction.atomic
@login_required
def challenge_evaluation_view(request, slug=None, challenge_id=None):
    if request.user.is_staff:
        messages.info(request, 'Vous ne pouvez pas passer d\'évaluation en tant que membre du personnel.')
        return redirect('home')
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
            'challenges': challenges,
        }
        return render(request, 'challenges/evaluation_choose.html', context)

    challenge = get_object_or_404(Challenge, slug=slug, id=challenge_id)

    attempt, _ = SubmissionAttempt.objects.get_or_create(candidate=request.user, challenge=challenge)
    if attempt.is_finished:
        messages.warning(request, 'Cette évaluation a déjà été terminée.')
        return redirect('result-detail', submission_id=attempt.submission.id, slug=challenge.slug,
                        challenge_id=challenge.id)

    time_left = max(attempt.remaining_time.total_seconds(), 0)

    context = {
        'challenge': challenge,
        'open_answer_questions': challenge.questions.filter(question_type=Question.QuestionType.OPEN_ANSWER),
        'choices_questions': challenge.questions.exclude(question_type=Question.QuestionType.OPEN_ANSWER),
        'time_left': math.ceil(time_left)
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
    mail_managers(
        subject=f'Nouvelle soumission pour le challenge {challenge.title}',
        message=f'Une nouvelle soumission a été faite pour le challenge {challenge.title} '
                f'par le candidat {submission.candidate.first_name} {submission.candidate.last_name}.'
                f' Soumission ID: {submission.id}.'
                f'Voir dans admin: {request.build_absolute_uri(reverse("admin:challenges_submission_change", args=[submission.id]))}',
        fail_silently=False,
    )
    try:
        correct_submission(submission)
        return redirect(
            'result-detail',
            challenge_id=submission.challenge.id,
            slug=submission.challenge.slug,
            submission_id=submission.id,
        )
    except:
        url = request.build_absolute_uri(reverse("admin:challenges_submission_change", args=[submission.id]))
        mail_managers(
            subject=f'Erreur lors de la correction de la soumission {submission.id}',
            message=f'Une erreur est survenue lors de la correction de la soumission {submission.id} '
                    f'pour le candidat {submission.candidate.first_name} {submission.candidate.last_name}.'
                    f' Challenge: {submission.challenge.title}.'
                    f'Voir dans admin: {url}',
            fail_silently=False,
        )
        messages.success(request, 'Réponses envoyées avec success')
        return render(request, 'challenges/home.html')
