from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import UserRegisterForm, UserUpdateForm, UserSkillFormSet

User = get_user_model()


def register_view(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, "Inscription réussie ! Bienvenue 😊")
            return redirect('home')  # Rediriger vers la page d'accueil ou tableau de bord
    else:
        form = UserRegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password,
                            backend='django.contrib.auth.backends.ModelBackend')
        if user is not None:
            login(request, user)
            return redirect('home')  # Rediriger vers la page d'accueil ou une autre page après connexion
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('home')


@login_required
def update_profile(request):
    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        skill_formset = UserSkillFormSet(request.POST, instance=request.user)
        if user_form.is_valid() and skill_formset.is_valid():
            user = user_form.save()
            skills = skill_formset.save()

            return redirect('challenge_evaluation')
        else:
            print(user_form.errors)
            print(skill_formset.errors)
    else:
        user_form = UserUpdateForm(instance=request.user)
        skill_formset = UserSkillFormSet(instance=request.user)

    return render(request, 'accounts/profile.html', {
        'user_form': user_form,
        'skill_formset': skill_formset,
    })
