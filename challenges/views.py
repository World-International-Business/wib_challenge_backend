import logging
import math
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.mail import EmailMultiAlternatives, mail_managers
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils import timezone
from django.utils.safestring import mark_safe

from accounts.models import User
from challenges.challenge_gen import generate_challenge_for_user, generate_personality_challenge_for_user, \
    generate_logical_challenge_for_user
from challenges.corrector import correct_submission, correct_personality_challenge
from challenges.models import (
    CampaignCandidate, Challenge, RecruitmentCampaign, SubmissionAttempt,
    Submission, Answer, PersonalityChallenge, PersonalityAnswer, TestDurationProfile,
)
from questions.models import Domain, Question

logger = logging.getLogger(__name__)


def _is_recruitment_staff(user):
    return user.is_authenticated and user.is_staff and not hasattr(user, 'school_staff')


recruitment_staff_required = user_passes_test(_is_recruitment_staff)


def _public_url(request, path):
    base_url = getattr(settings, 'PUBLIC_SITE_URL', '').rstrip('/')
    if base_url:
        return f'{base_url}{path}'
    if not settings.DEBUG:
        raise RuntimeError('PUBLIC_SITE_URL doit être configurée en production')
    return request.build_absolute_uri(path)


def _send_candidate_invitation(request, candidate, campaign=None):
    uid = urlsafe_base64_encode(force_bytes(candidate.pk))
    token = default_token_generator.make_token(candidate)
    reset_path = reverse('password_reset_confirm', kwargs={
        'uidb64': uid,
        'token': token,
    })
    reset_url = _public_url(request, reset_path)
    site_url = _public_url(request, reverse('home'))
    campaign_url = _public_url(request, reverse('recruitment_campaign_access', kwargs={'campaign_id': campaign.id})) if campaign else ''
    email = EmailMultiAlternatives(
        'Votre invitation à WIB Challenge',
        (
            f'Bonjour {candidate.first_name},\n\n'
            'Vous êtes invité(e) à passer vos évaluations en ligne sur la plateforme WIB Challenge.\n\n'
            'Commencez par définir votre mot de passe avec ce lien : '
            f'{reset_url}\n\nAccéder à la plateforme : {site_url}\n\n'
            'Ce lien est personnel. Si vous n\'êtes pas à l\'origine de cette invitation, '
            'ignorez ce message.'
        ),
        None,
        [candidate.email],
    )
    email.attach_alternative(
        render_to_string('challenges/candidate_invitation_email.html', {
            'first_name': candidate.first_name,
            'reset_url': reset_url,
            'site_url': site_url,
            'campaign_url': campaign_url,
        }),
        'text/html',
    )
    email.send(fail_silently=False)


def _send_recruitment_message(request, recipient, first_name, subject, message, registration_url=None, include_registration=False, campaign=None):
    if include_registration and registration_url is None:
        params = {'email': recipient}
        if campaign:
            params['campaign'] = campaign.id
        register_path = f'{reverse("register")}?{urlencode(params)}'
        registration_url = _public_url(request, register_path)
    plain_message = f'Bonjour {first_name},\n\n{message}'
    if registration_url:
        plain_message += f'\n\nCréer mon accès : {registration_url}'
    email = EmailMultiAlternatives(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
    )
    email.attach_alternative(
        render_to_string('challenges/candidate_personal_email.html', {
            'first_name': first_name,
            'subject': subject,
            'message': message,
            'registration_url': registration_url,
        }),
        'text/html',
    )
    email.send(fail_silently=False)


def home_view(request):
    if not request.user.is_authenticated:
        return render(request, 'challenges/home.html')
    context = {
        'latest_challenges': Challenge.objects.filter(submissions__candidate=request.user).prefetch_related(
            'submissions')
    }
    return render(request, 'challenges/home.html', context)


def recruitment_campaign_access_view(request, campaign_id):
    campaign = get_object_or_404(RecruitmentCampaign, id=campaign_id, status=RecruitmentCampaign.Status.OPEN)
    request.session['recruitment_campaign_id'] = campaign.id
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect('challenge_evaluation')


@recruitment_staff_required
def recruitment_campaign_list_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        position = request.POST.get('position', '').strip()
        description = request.POST.get('description', '').strip()
        if not name or not position:
            messages.error(request, 'Le nom de la campagne et le poste sont obligatoires.')
        else:
            campaign = RecruitmentCampaign.objects.create(
                owner=request.user,
                name=name,
                position=position,
                description=description,
                status=RecruitmentCampaign.Status.OPEN,
            )
            messages.success(request, f'La campagne « {campaign.name} » a été créée.')
            return redirect('recruitment_campaign_detail', campaign_id=campaign.id)
    campaigns = RecruitmentCampaign.objects.prefetch_related('candidates').order_by('-created_at')
    return render(request, 'challenges/campaign_list.html', {'campaigns': campaigns})


@recruitment_staff_required
def recruitment_campaign_detail_view(request, campaign_id):
    campaign = get_object_or_404(RecruitmentCampaign, id=campaign_id)
    memberships = campaign.candidates.select_related('candidate').order_by('-invited_at')
    submissions = campaign.submissions.select_related('candidate', 'challenge').order_by('-submitted_at')
    personalities = campaign.personality_challenges.select_related('candidate').order_by('-created_at')
    return render(request, 'challenges/campaign_detail.html', {
        'campaign': campaign,
        'memberships': memberships,
        'submissions': submissions,
        'personalities': personalities,
    })


@recruitment_staff_required
def admin_dashboard_view(request):
    candidates = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
    )
    technical_count = Submission.objects.filter(challenge__is_logical=False).count()
    logical_count = Submission.objects.filter(challenge__is_logical=True).count()
    personality_count = PersonalityChallenge.objects.filter(is_passed=True).count()
    duration_profiles = TestDurationProfile.objects.select_related('domain').all()[:10]

    # Filtres pour les derniers résultats
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    candidate_search = request.GET.get('candidate_search', '').strip()

    latest_submissions = Submission.objects.select_related('candidate', 'challenge').order_by('-submitted_at')
    if date_from:
        latest_submissions = latest_submissions.filter(submitted_at__date__gte=date_from)
    if date_to:
        latest_submissions = latest_submissions.filter(submitted_at__date__lte=date_to)
    if type_filter == 'technical':
        latest_submissions = latest_submissions.filter(challenge__is_logical=False)
    elif type_filter == 'logical':
        latest_submissions = latest_submissions.filter(challenge__is_logical=True)
    if status_filter == 'corrected':
        latest_submissions = latest_submissions.filter(status=Submission.CorrectionStatus.CORRECTED)
    elif status_filter == 'pending':
        latest_submissions = latest_submissions.filter(status=Submission.CorrectionStatus.PENDING)
    if candidate_search:
        latest_submissions = latest_submissions.filter(
            Q(candidate__first_name__icontains=candidate_search) |
            Q(candidate__last_name__icontains=candidate_search) |
            Q(candidate__email__icontains=candidate_search)
        )

    page = request.GET.get('page', 1)
    paginator = Paginator(latest_submissions, 10)
    try:
        latest_submissions = paginator.page(page)
    except PageNotAnInteger:
        latest_submissions = paginator.page(1)
    except EmptyPage:
        latest_submissions = paginator.page(paginator.num_pages)

    # Compteurs de questions par domaine et par type de test
    question_counts = {}
    for row in Question.objects.values('category__domain', 'question_category').annotate(count=Count('id')):
        domain_counts = question_counts.setdefault(row['category__domain'], {})
        domain_counts[row['question_category']] = row['count']

    domain_stats = []
    for domain in Domain.objects.prefetch_related('durations').order_by('name'):
        counts = question_counts.get(domain.id, {})
        domain_stats.append({
            'domain': domain,
            'normal': counts.get('NORMAL', 0),
            'logical': counts.get('LOGICAL', 0),
            'personality': counts.get('PERSONALITY', 0),
            'total': sum(counts.values()),
        })

    context = {
        'candidates_count': candidates.count(),
        'technical_count': technical_count,
        'logical_count': logical_count,
        'personality_count': personality_count,
        'latest_submissions': latest_submissions,
        'duration_profiles': duration_profiles,
        'domain_stats': domain_stats,
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'type': type_filter,
            'status': status_filter,
            'candidate_search': candidate_search,
        },
    }
    return render(request, 'challenges/admin_dashboard.html', context)


@login_required
def evaluation_results(request, submission_id=None, slug=None, challenge_id=None):
    candidate = request.user
    if _is_recruitment_staff(request.user) and request.GET.get('user_id', None):
        candidate = get_object_or_404(User, pk=request.GET.get('user_id'))
    if not slug or not challenge_id:
        is_admin = _is_recruitment_staff(request.user) and candidate == request.user
        if is_admin:
            submissions = Submission.objects.all()
        else:
            submissions = User.objects.get(id=candidate.id).submissions.all()

        submissions = submissions.prefetch_related('challenge').select_related('candidate').order_by('-submitted_at')

        # Filtres admin
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        challenge_id_filter = request.GET.get('challenge')
        candidate_id_filter = request.GET.get('candidate')

        if date_from:
            submissions = submissions.filter(submitted_at__date__gte=date_from)
        if date_to:
            submissions = submissions.filter(submitted_at__date__lte=date_to)
        if challenge_id_filter:
            submissions = submissions.filter(challenge_id=challenge_id_filter)
        if candidate_id_filter:
            submissions = submissions.filter(candidate_id=candidate_id_filter)

        # paginate
        page = request.GET.get('page', 1)
        paginator = Paginator(submissions, 20)
        try:
            submissions = paginator.page(page)
        except PageNotAnInteger:
            submissions = paginator.page(1)
        except EmptyPage:
            submissions = paginator.page(paginator.num_pages)

        if is_admin:
            personality_results = PersonalityChallenge.objects.all()
            if candidate_id_filter:
                personality_results = personality_results.filter(candidate_id=candidate_id_filter)
        else:
            personality_results = candidate.personality_challenges.all()
        personality_results = personality_results.order_by('-created_at', '-id')
        personality_page = Paginator(personality_results, 10).get_page(
            request.GET.get('personality_page')
        )
        total_evaluations = submissions.paginator.count + personality_results.count()

        context = {
            'submissions': submissions,
            'personality_results': personality_page,
            'total_evaluations': total_evaluations,
            'add_id': _is_recruitment_staff(request.user),
            'is_admin': is_admin,
            'challenges': Challenge.objects.all().order_by('title') if is_admin else [],
            'candidates': User.objects.filter(
                is_staff=False,
                is_superuser=False,
                student_profile__isnull=True,
                school_staff__isnull=True,
            ).order_by('last_name', 'first_name') if is_admin else [],
            'filters': {
                'date_from': date_from or '',
                'date_to': date_to or '',
                'challenge': challenge_id_filter or '',
                'candidate': candidate_id_filter or '',
            },
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
def personality_evaluation_view(request):
    if request.user.is_staff:
        messages.info(request, 'Vous ne pouvez pas passer d\'évaluation en tant que membre du personnel.')
        return redirect('personality_candidates')

    if request.user.personality_challenges.exists():
        challenge = request.user.personality_challenges.first()
    else:
        if request.user.domain:
            challenge = generate_personality_challenge_for_user(request.user, request.user.domain)
        else:
            messages.info(request, 'Veuillez sélectionner un domaine avant de continuer.')
            return redirect('update_profile')

    if challenge.corrected or challenge.is_passed or challenge.answers.exists():
        messages.info(request, 'Vous avez déjà passé cette évaluation.')
        return redirect('home')

    time_left = max(challenge.duration.total_seconds(), 0) if challenge.duration else 0

    context = {
        'challenge': challenge,
        'open_answer_questions': challenge.questions.filter(question_type=Question.QuestionType.OPEN_ANSWER),
        'choices_questions': challenge.questions.exclude(question_type=Question.QuestionType.OPEN_ANSWER),
        'time_left': math.ceil(time_left),
    }
    return render(request, 'challenges/personallity_evaluation.html', context)


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
        challenges = User.objects.get(id=request.user.id).challenges.filter(
            is_logical=False, questions__isnull=False
        ).exclude(submissions__candidate_id=request.user.id).distinct()
        if challenges.count() == 0:
            challenges = Challenge.objects.filter(
                is_logical=False, attempts__candidate=request.user, attempts__ended_at__isnull=True, questions__isnull=False
            ).distinct()

        challenges = challenges.order_by('title')

        page = request.GET.get('page', 1)
        paginator = Paginator(challenges, 20)
        try:
            challenges = paginator.page(page)
        except PageNotAnInteger:
            challenges = paginator.page(1)
        except EmptyPage:
            challenges = paginator.page(paginator.num_pages)

        personality_challenge = PersonalityChallenge.objects.filter(candidate=request.user).first()
        has_personality_test = personality_challenge is not None
        personality_passed = has_personality_test and (
            personality_challenge.corrected or
            personality_challenge.is_passed or
            personality_challenge.answers.exists()
        )

        logical_challenge = Challenge.objects.filter(
            is_logical=True,
            users=request.user
        ).first()
        has_logical_test = logical_challenge is not None
        logical_passed = has_logical_test and logical_challenge.submissions.filter(
            candidate=request.user
        ).exists()

        technical_passed = Submission.objects.filter(
            candidate=request.user,
            challenge__is_logical=False
        ).exists()

        context = {
            'domain': request.user.domain.name,
            'challenges': challenges,
            'personality_challenge': personality_challenge,
            'has_personality_test': has_personality_test,
            'personality_passed': personality_passed,
            'logical_challenge': logical_challenge,
            'has_logical_test': has_logical_test,
            'logical_passed': logical_passed,
            'technical_passed': technical_passed,
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
def submit_evaluation_view(request):
    if request.method != 'POST':
        return redirect('home')

    is_challenge = request.POST.get('personality', None) is None
    admin_url = "admin:challenges_submission_change" if is_challenge else "admin:challenges_personalitychallenge_change"
    _Challenge = Challenge if is_challenge else PersonalityChallenge
    _Answer = Answer if is_challenge else PersonalityAnswer
    _correct_submission = correct_submission if is_challenge else correct_personality_challenge
    answers = []

    challenge = get_object_or_404(_Challenge,
                                  id=request.POST.get('challenge_id'))
    campaign = None
    campaign_id = request.session.get('recruitment_campaign_id')
    if campaign_id:
        campaign = RecruitmentCampaign.objects.filter(
            id=campaign_id,
            status=RecruitmentCampaign.Status.OPEN,
            candidates__candidate=request.user,
        ).first()
    if is_challenge:
        submission = Submission.objects.create(
            candidate=request.user,
            challenge=challenge,
            campaign=campaign,
        )
        attempt, _ = SubmissionAttempt.objects.get_or_create(
            candidate=request.user,
            challenge=challenge,
            defaults={'campaign': campaign},
        )
        if campaign and attempt.campaign_id != campaign.id:
            attempt.campaign = campaign
        attempt.ended_at = timezone.now()
        attempt.submission = submission
        attempt.save()
    else:
        submission = challenge
        if campaign and submission.campaign_id != campaign.id:
            submission.campaign = campaign

    for key in request.POST:
        if key.startswith('answer_'):
            question_id = int(key.split('_')[-1])
            values = list(filter(lambda x: bool(x), request.POST.getlist(key, [])))
            if not values:
                continue
            question = get_object_or_404(Question, id=question_id)
            if question.question_type == Question.QuestionType.OPEN_ANSWER:
                answers.append(
                    _Answer.objects.create(
                        submission=submission,
                        question=question,
                        text=values[0]
                    )
                )
            else:
                answer = _Answer.objects.create(
                    submission=submission,
                    question=question,
                )
                answer.selected_choices.set(values)
                answers.append(answer)
    if hasattr(submission, 'is_passed'):
        submission.is_passed = True
    if not is_challenge:
        challenge.is_passed = True
    submission.save()
    mail_managers(
        subject=f"Nouvelle soumission pour le {'challenge' if is_challenge else 'personality_challenge'} {challenge.title}",
        message=f'Une nouvelle soumission a été faite pour le challenge {challenge.title} '
                f'par le candidat {submission.candidate.first_name} {submission.candidate.last_name}.'
                f' Soumission ID: {submission.id}.'
                f'Voir dans admin: {request.build_absolute_uri(reverse(admin_url, args=[submission.id]))}',
        fail_silently=True,
    )
    result_url = request.build_absolute_uri(reverse(
        'result-detail',
        kwargs={
            'submission_id': submission.id,
            'slug': challenge.slug,
            'challenge_id': challenge.id
        }
    ))
    success_msg = 'Vos réponses ont bien été enregistrées.'
    if is_challenge:
        success_msg += f' <a href="{result_url}" class="alert-link">Voir le résultat</a>'
    messages.success(request, mark_safe(success_msg))

    # La correction est lancée après le commit de la requête afin de ne pas
    # bloquer l'enregistrement si l'API Gemini rencontre un problème.
    def run_correction():
        try:
            _correct_submission(submission)
        except Exception:
            logger.exception('Erreur lors de la correction %s', submission.id)

    try:
        transaction.on_commit(run_correction)
    except Exception:
        logger.exception('Erreur lors de la planification de la correction %s', submission.id)
        messages.info(
            request,
            'Vos réponses ont bien été enregistrées. Elles seront corrigées sous peu. '
            'Merci de votre patience.'
        )
    return render(request, 'challenges/home.html')


def generate_challenge(request):
    if request.method != 'POST' or not request.user.has_skill_infos or request.user.is_staff:
        return redirect('home')
    if Submission.objects.filter(candidate=request.user, challenge__is_logical=False).exists():
        messages.warning(request, 'Vous avez déjà passé un test technique. Pour le repasser, contactez l\'administrateur.')
        return redirect('home')
    challenge = generate_challenge_for_user(request.user)
    request.user.challenges.add(challenge)
    if request.user.challenges.filter(is_logical=True).count() == 0:
        logical_challenge = generate_logical_challenge_for_user(request.user)
        request.user.challenges.add(logical_challenge)
    if request.user.personality_challenges.count() == 0:
        generate_personality_challenge_for_user(request.user, request.user.domain)
    return HttpResponse()


def generate_personality_challenge(request):
    if request.method != 'POST' or not request.user.has_skill_infos or request.user.is_staff:
        return redirect('home')

    if PersonalityChallenge.objects.filter(candidate=request.user).exists():
        messages.info(request, 'Vous avez déjà un test de personnalité disponible.')
        return HttpResponse()

    challenge = generate_personality_challenge_for_user(request.user, request.user.domain)
    request.user.personality_challenges.add(challenge)
    return HttpResponse()


def generate_logical_challenge(request):
    if request.method != 'POST' or not request.user.has_skill_infos or request.user.is_staff:
        return redirect('home')

    # Vérifier si l'utilisateur a déjà un test logique
    if Challenge.objects.filter(
            is_logical=True,
            users=request.user
    ).exists():
        messages.info(request, 'Vous avez déjà un test logique disponible.')
        return HttpResponse()

    challenge = generate_logical_challenge_for_user(request.user)
    request.user.challenges.add(challenge)
    return HttpResponse()


@login_required
def personality_details_view(request, user_id=None):
    """Vue pour afficher les détails de personnalité (candidat: soi-même, admin: tout le monde)."""

    if request.user.is_staff and not _is_recruitment_staff(request.user):
        return redirect('home')

    if not request.user.is_staff:
        if not user_id or user_id != request.user.id:
            return redirect('personality_details', user_id=request.user.id)

    if user_id:
        candidate = get_object_or_404(User, id=user_id)
        personality_challenges = PersonalityChallenge.objects.filter(
            candidate=candidate,
            corrected=True
        ).order_by('-id')
        personality_page = Paginator(personality_challenges, 5).get_page(
            request.GET.get('personality_page')
        )

        context = {
            'candidate': candidate,
            'personality_challenges': personality_page,
        }
        return render(request, 'challenges/personality_detail.html', context)

    # Récupérer tous les utilisateurs qui ont un test de personnalité
    users_with_challenges = User.objects.filter(
        personality_challenges__isnull=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
    ).distinct().order_by('last_name', 'first_name')

    # Ajouter des informations sur le statut des tests
    for user in users_with_challenges:
        challenges = PersonalityChallenge.objects.filter(candidate=user)
        user.has_corrected_challenge = challenges.filter(corrected=True).exists()
        user.has_passed_challenge = challenges.filter(is_passed=True).exists()
        user.total_challenges = challenges.count()
        user.corrected_challenges = challenges.filter(corrected=True).count()

    paginator = Paginator(users_with_challenges, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'challenges/personality_candidates.html', context)


@recruitment_staff_required
def manual_correct_submission_view(request, submission_id):
    """Relance manuellement la correction d'une soumission technique/psychotechnique."""
    submission = get_object_or_404(Submission, id=submission_id)
    correct_submission(submission)
    messages.success(request, f'Correction relancée pour {submission.challenge.title}.')
    return redirect(request.GET.get('next', 'results'))


@recruitment_staff_required
def manual_correct_personality_view(request, personality_id):
    """Relance manuellement la correction d'un test de personnalité."""
    challenge = get_object_or_404(PersonalityChallenge, id=personality_id)
    correct_personality_challenge(challenge)
    if challenge.corrected:
        messages.success(request, f'Correction terminée pour {challenge.title}.')
    else:
        messages.error(
            request,
            "La correction n'a pas abouti. Consultez les logs du serveur pour connaître la cause."
        )

    if request.GET.get('next') == 'personality_details':
        return redirect('personality_details', user_id=challenge.candidate_id)
    return redirect(request.GET.get('next', 'personality_candidates'))


@recruitment_staff_required
def candidate_list_view(request):
    candidates = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
    ).order_by('last_name', 'first_name', 'email')
    search = request.GET.get('search', '').strip()
    campaign_id = (request.POST.get('campaign') or request.GET.get('campaign', '')).strip()
    campaign = get_object_or_404(RecruitmentCampaign, id=campaign_id) if campaign_id else None
    if search:
        candidates = candidates.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )

    if request.method == 'POST':
        selected_ids = request.POST.getlist('candidate_ids')
        selected_candidates = candidates.filter(id__in=selected_ids)
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        raw_manual_emails = request.POST.get('manual_emails', '')
        manual_emails = []
        for value in re.split(r'[,;\s]+', raw_manual_emails):
            email = value.strip().lower()
            if email and email not in manual_emails:
                manual_emails.append(email)
        invalid_emails = []
        valid_manual_emails = []
        for email in manual_emails:
            try:
                validate_email(email)
            except ValidationError:
                invalid_emails.append(email)
            else:
                valid_manual_emails.append(email)

        if valid_manual_emails and (not subject or not message):
            messages.error(request, 'Le sujet et le message sont obligatoires pour un envoi personnalisé.')
            return redirect(reverse('candidate_list'))

        sent = 0
        failed = 0
        for candidate in selected_candidates:
            if campaign:
                CampaignCandidate.objects.get_or_create(campaign=campaign, candidate=candidate)
            try:
                if subject and message:
                    _send_recruitment_message(request, candidate.email, candidate.first_name or 'candidat', subject, message)
                else:
                    _send_candidate_invitation(request, candidate, campaign=campaign)
                sent += 1
            except Exception:
                failed += 1
                logger.exception('Erreur lors de l invitation du candidat %s', candidate.pk)

        registered_emails = {candidate.email.lower() for candidate in selected_candidates}
        for email in valid_manual_emails:
            if email in registered_emails:
                continue
            try:
                existing_candidate = candidates.filter(email__iexact=email).first()
                if existing_candidate:
                    _send_recruitment_message(
                        request,
                        email,
                        existing_candidate.first_name or 'candidat',
                        subject,
                        message,
                        registration_url=None,
                    )
                else:
                    _send_recruitment_message(
                        request,
                        email,
                        email.split('@')[0],
                        subject,
                        message,
                        include_registration=True,
                        campaign=campaign,
                    )
                sent += 1
            except Exception:
                failed += 1
                logger.exception('Erreur lors de l envoi manuel à %s', email)

        if sent:
            messages.success(request, f'{sent} invitation(s) envoyée(s) avec succès.')
        if failed:
            messages.error(request, f'{failed} invitation(s) n’ont pas pu être envoyée(s).')
        if invalid_emails:
            messages.warning(request, f'{len(invalid_emails)} adresse(s) ignorée(s) car invalide(s).')
        if not selected_ids and not valid_manual_emails:
            messages.warning(request, 'Sélectionnez un candidat ou saisissez au moins une adresse email.')
        query_values = {}
        if search:
            query_values['search'] = search
        if campaign:
            query_values['campaign'] = campaign.id
        query = urlencode(query_values)
        return redirect(f'{reverse("candidate_list")}?{query}' if query else reverse('candidate_list'))

    page_obj = Paginator(candidates, 20).get_page(request.GET.get('page'))
    return render(request, 'challenges/candidate_list.html', {
        'page_obj': page_obj,
        'search': search,
        'campaign': campaign,
    })


@recruitment_staff_required
def candidate_detail_view(request, user_id):
    """Vue détaillée d'un candidat avec ses 3 types d'évaluations."""
    candidate = get_object_or_404(
        User,
        id=user_id,
        is_staff=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
    )

    technical_submissions = Submission.objects.filter(
        candidate=candidate,
        challenge__is_logical=False
    ).select_related('challenge').order_by('-submitted_at')

    logical_submissions = Submission.objects.filter(
        candidate=candidate,
        challenge__is_logical=True
    ).select_related('challenge').order_by('-submitted_at')

    personality_challenges = PersonalityChallenge.objects.filter(
        candidate=candidate
    ).order_by('-id')

    technical_page = Paginator(technical_submissions, 10).get_page(request.GET.get('technical_page'))
    logical_page = Paginator(logical_submissions, 10).get_page(request.GET.get('logical_page'))
    personality_page = Paginator(personality_challenges, 10).get_page(request.GET.get('personality_page'))

    context = {
        'candidate': candidate,
        'technical_count': technical_submissions.count(),
        'logical_count': logical_submissions.count(),
        'personality_count': personality_challenges.count(),
        'technical_submissions': technical_page,
        'logical_submissions': logical_page,
        'personality_challenges': personality_page,
    }
    return render(request, 'challenges/candidate_detail.html', context)


@recruitment_staff_required
def candidate_retake_view(request, user_id):
    """Autorise un candidat à repasser un test (supprime/dissocie l'ancien)."""
    candidate = get_object_or_404(
        User,
        id=user_id,
        is_staff=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
    )
    test_type = request.POST.get('test_type') or request.GET.get('test_type')

    if request.method == 'POST' and test_type:
        if test_type == 'technical':
            for challenge in candidate.challenges.filter(is_logical=False):
                if challenge.submissions.filter(candidate=candidate).exists():
                    candidate.challenges.remove(challenge)
                else:
                    challenge.delete()
            messages.success(request, 'Un nouveau test technique peut être généré.')
        elif test_type == 'logical':
            for challenge in candidate.challenges.filter(is_logical=True):
                if challenge.submissions.filter(candidate=candidate).exists():
                    candidate.challenges.remove(challenge)
                else:
                    challenge.delete()
            messages.success(request, 'Un nouveau test psychotechnique peut être généré.')
        elif test_type == 'personality':
            candidate.personality_challenges.all().delete()
            messages.success(request, 'Un nouveau test de personnalité peut être généré.')

    return redirect('candidate_detail', user_id=candidate.id)


@recruitment_staff_required
def candidate_invitation_view(request, user_id):
    if request.method != 'POST':
        return redirect('candidate_detail', user_id=user_id)

    candidate = get_object_or_404(
        User,
        id=user_id,
        is_staff=False,
        is_superuser=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
    )
    try:
        _send_candidate_invitation(request, candidate)
    except Exception:
        logger.exception('Erreur lors de l invitation du candidat %s', candidate.pk)
        messages.error(request, "L'invitation n'a pas pu être envoyée. Vérifiez la configuration email.")
    else:
        messages.success(request, f"L'invitation a été envoyée à {candidate.email}.")

    return redirect('candidate_detail', user_id=candidate.id)


@recruitment_staff_required
def candidate_message_view(request, user_id):
    candidate = get_object_or_404(
        User,
        id=user_id,
        is_staff=False,
        is_superuser=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
    )
    if request.method != 'POST':
        return redirect('candidate_detail', user_id=candidate.id)

    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()
    if not subject or not message:
        messages.error(request, 'Le sujet et le message sont obligatoires.')
        return redirect('candidate_detail', user_id=candidate.id)

    try:
        email = EmailMultiAlternatives(
            subject,
            f'Bonjour {candidate.first_name},\n\n{message}',
            settings.DEFAULT_FROM_EMAIL,
            [candidate.email],
        )
        email.attach_alternative(
            render_to_string('challenges/candidate_personal_email.html', {
                'first_name': candidate.first_name,
                'subject': subject,
                'message': message,
            }),
            'text/html',
        )
        email.send(fail_silently=False)
    except Exception:
        logger.exception('Erreur lors de l envoi du message au candidat %s', candidate.pk)
        messages.error(request, "Le message n'a pas pu être envoyé.")
    else:
        messages.success(request, f'Le message a été envoyé à {candidate.email}.')

    return redirect('candidate_detail', user_id=candidate.id)


@recruitment_staff_required
def leaderboard_view(request):
    """Classement des candidats sur les 3 types d'évaluation."""
    domain_id = request.GET.get('domain')

    candidates = User.objects.filter(
        is_staff=False,
        student_profile__isnull=True,
        school_staff__isnull=True,
        submissions__isnull=False
    ).distinct()

    if domain_id:
        candidates = candidates.filter(domain_id=domain_id)

    leaderboard = []
    for candidate in candidates:
        tech_score = candidate.submissions.filter(
            challenge__is_logical=False,
            result__isnull=False
        ).aggregate(avg=Avg('result'))['avg'] or 0

        psych_score = candidate.submissions.filter(
            challenge__is_logical=True,
            result__isnull=False
        ).aggregate(avg=Avg('result'))['avg'] or 0

        personality_done = candidate.personality_challenges.filter(corrected=True).exists()

        overall = (tech_score + psych_score) / 2

        leaderboard.append({
            'candidate': candidate,
            'tech_score': tech_score,
            'psych_score': psych_score,
            'personality_done': personality_done,
            'overall': overall,
        })

    leaderboard.sort(key=lambda x: x['overall'], reverse=True)
    leaderboard_page = Paginator(leaderboard, 20).get_page(request.GET.get('page'))

    domains = Domain.objects.filter(
        user__is_staff=False,
        user__is_superuser=False,
        user__student_profile__isnull=True,
        user__school_staff__isnull=True,
    ).distinct().order_by('name')

    context = {
        'leaderboard': leaderboard_page,
        'domains': domains,
        'domain_id': domain_id or '',
    }
    return render(request, 'challenges/leaderboard.html', context)
