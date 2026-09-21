import secrets
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone

from .forms import UserRegisterForm, EmailVerificationForm, UserUpdateForm, SimpleUserUpdateForm, UserSkillFormSet, WIBPasswordResetForm, WIBSetPasswordForm

User = get_user_model()
logger = logging.getLogger(__name__)


def register_view(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    user.email_verified = False
                    user.save()
                    code = f'{secrets.randbelow(1000000):06d}'
                    email_context = {
                        'code': code,
                        'first_name': user.first_name,
                    }
                    email = EmailMultiAlternatives(
                        'Votre code de vérification WIB Challenge',
                        (
                            f"Bonjour {user.first_name},\n\n"
                            f"Votre code de vérification est : {code}.\n"
                            "Il expire dans 15 minutes.\n\n"
                            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email."
                        ),
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                    )
                    email.attach_alternative(
                        render_to_string('accounts/verification_email.html', email_context),
                        'text/html',
                    )
                    email.send(fail_silently=False)
            except Exception:
                logger.exception('Erreur lors de l envoi du code de vérification')
                messages.error(
                    request,
                    "Impossible d'envoyer l'email de vérification. "
                    "Vérifiez votre adresse email ou réessayez plus tard.",
                )
                return render(request, 'accounts/register.html', {'form': form})

            request.session['verification_user_id'] = user.pk
            request.session['verification_code'] = code
            request.session['verification_expires_at'] = (timezone.now() + timedelta(minutes=15)).timestamp()
            messages.info(request, "Un code de vérification a été envoyé à votre adresse email.")
            return redirect('verify_email')
    else:
        campaign_id = request.GET.get('campaign', '').strip()
        if campaign_id.isdigit():
            request.session['recruitment_campaign_id'] = int(campaign_id)
        form = UserRegisterForm(initial={'email': request.GET.get('email', '').strip()})

    return render(request, 'accounts/register.html', {'form': form})


def verify_email_view(request):
    user_id = request.session.get('verification_user_id')
    if not user_id:
        return redirect('register')
    if request.method == 'POST':
        form = EmailVerificationForm(request.POST)
        expires_at = request.session.get('verification_expires_at', 0)
        if form.is_valid() and timezone.now().timestamp() <= expires_at and secrets.compare_digest(
                form.cleaned_data['code'], request.session.get('verification_code', '')):
            user = User.objects.get(pk=user_id)
            user.email_verified = True
            user.is_active = True
            user.save(update_fields=['email_verified', 'is_active'])
            campaign_id = request.session.get('recruitment_campaign_id')
            if campaign_id:
                from challenges.models import CampaignCandidate, RecruitmentCampaign

                campaign = RecruitmentCampaign.objects.filter(
                    id=campaign_id,
                    status=RecruitmentCampaign.Status.OPEN,
                ).first()
                if campaign:
                    CampaignCandidate.objects.get_or_create(campaign=campaign, candidate=user)
            request.session.pop('verification_user_id', None)
            request.session.pop('verification_code', None)
            request.session.pop('verification_expires_at', None)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, "Adresse email vérifiée. Bienvenue !")
            return redirect('challenge_evaluation')
        form.add_error('code', "Code incorrect ou expiré.")
    else:
        form = EmailVerificationForm()
    return render(request, 'accounts/verify_email.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password,
                            backend='django.contrib.auth.backends.ModelBackend')
        if user is not None:
            login(request, user)
            if hasattr(user, 'school_staff'):
                return redirect('school_dashboard')
            if hasattr(user, 'student_profile'):
                return redirect('student_dashboard')
            return redirect('challenge_evaluation')
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('home')


@transaction.atomic
@login_required
def update_profile(request):
    # Redirect to appropriate profile based on user type
    if hasattr(request.user, 'student_profile'):
        return redirect('student_profile')
    elif hasattr(request.user, 'school_staff'):
        return redirect('school_staff_profile')
    else:
        return redirect('candidate_profile')


@login_required
def student_profile_view(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('update_profile')
    
    student = request.user.student_profile
    if request.method == "POST":
        user_form = SimpleUserUpdateForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Votre profil a ete mis a jour.')
            return redirect('student_profile')
    else:
        user_form = SimpleUserUpdateForm(instance=request.user)

    return render(request, 'accounts/student_profile.html', {
        'user_form': user_form,
        'student': student,
    })


@login_required
def school_staff_profile_view(request):
    if not hasattr(request.user, 'school_staff'):
        return redirect('update_profile')
    
    staff = request.user.school_staff
    if request.method == "POST":
        user_form = SimpleUserUpdateForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Votre profil a ete mis a jour.')
            return redirect('school_staff_profile')
    else:
        user_form = SimpleUserUpdateForm(instance=request.user)

    return render(request, 'accounts/school_staff_profile.html', {
        'user_form': user_form,
        'staff': staff,
    })


@login_required
def candidate_profile_view(request):
    if hasattr(request.user, 'student_profile') or hasattr(request.user, 'school_staff'):
        return redirect('update_profile')
    
    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        skill_formset = UserSkillFormSet(request.POST, instance=request.user)
        if user_form.is_valid() and skill_formset.is_valid():
            user_form.save()
            skill_formset.save()
            messages.success(request, 'Votre profil a ete mis a jour.')
            return redirect('candidate_profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        skill_formset = UserSkillFormSet(instance=request.user)

    return render(request, 'accounts/candidate_profile.html', {
        'user_form': user_form,
        'skill_formset': skill_formset,
    })


# Vues pour la réinitialisation de mot de passe
class WIBPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    form_class = WIBPasswordResetForm
    email_template_name = 'accounts/password_reset_email.txt'
    html_email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')


class WIBPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class WIBPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    form_class = WIBSetPasswordForm
    success_url = reverse_lazy('password_reset_complete')


class WIBPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
