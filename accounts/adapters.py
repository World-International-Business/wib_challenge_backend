from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
User = get_user_model()

# ✅ Redirige vers la page d'accueil après connexion normale (email/password)
class MyAccountAdapter(DefaultAccountAdapter):
    def clean_username(self, username, shallow=False):
        return None  # Empêche Allauth de demander un username

    def get_login_redirect_url(self, request):
        return "/"

# ✅ Redirige vers la page d'accueil après connexion avec Google
class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email")
        if email:
            try:
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)  # Associe le compte existant au lieu de créer un nouveau
            except User.DoesNotExist:
                pass  # Aucun utilisateur existant, Django créera un nouvel utilisateur normalement

    def get_login_redirect_url(self, request):
        return "/"
