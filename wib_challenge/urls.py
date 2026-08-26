"""
URL configuration for wib_challenge project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import path

from accounts.views import (login_view, register_view, logout_view, update_profile,
                           WIBPasswordResetView, WIBPasswordResetDoneView,
                           WIBPasswordResetConfirmView, WIBPasswordResetCompleteView)
from challenges.views import home_view, evaluation_results, challenge_evaluation_view, submit_evaluation_view, \
    generate_challenge, generate_logical_challenge, generate_personality_challenge, personality_details_view, \
    personality_evaluation_view, candidate_detail_view, candidate_retake_view, leaderboard_view, admin_dashboard_view
from questions.models import Question
from wib_challenge.views import json_input

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tableau-de-bord/', admin_dashboard_view, name='admin_dashboard'),
    path('', home_view, name='home'),
    path('resultats/', evaluation_results, name='results'),
    path('resultats/<int:submission_id>-<slug:slug>-<int:challenge_id>',
         evaluation_results, name='result-detail'),
    path('evaluation/', challenge_evaluation_view, name='challenge_evaluation'),
    path('evaluation/personality/', personality_evaluation_view,
         name='personality_evaluation'),
    path('evaluation/<slug:slug>-<int:challenge_id>',
         challenge_evaluation_view, name='challenge_evaluation_detail'),
    path('submit_evaluation/', submit_evaluation_view, name='submit_evaluation'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('profile/update/', update_profile, name='update_profile'),
    path('add-questions/', json_input,
         {'question_category': Question.QuestionCategory.NORMAL}, name='add_questions'),
    path('add-questions/logical/', json_input,
         {'question_category': Question.QuestionCategory.LOGICAL}, name='add_logical_questions'),
    path('add-questions/personality/', json_input,
         {'question_category': Question.QuestionCategory.PERSONALITY}, name='add_personality_questions'),
    path('create-challenge/', generate_challenge, name='challenge_create'),
    path('create-challenge/logical/', generate_logical_challenge,
         name='logical_challenge_create'),
    path('create-challenge/personality/', generate_personality_challenge,
         name='personality_challenge_create'),

    # Nouvelles routes pour l'analyse de personnalité (admin uniquement)
    path('personalities/', personality_details_view,
         name='personality_candidates'),
    path('personalities/<int:user_id>/',
         personality_details_view, name='personality_details'),

    # Détail candidat et classement (admin)
    path('candidat/<int:user_id>/', candidate_detail_view, name='candidate_detail'),
    path('candidat/<int:user_id>/retake/', candidate_retake_view, name='candidate_retake'),
    path('classement/', leaderboard_view, name='leaderboard'),

    # URLs pour la réinitialisation de mot de passe
    path('password-reset/', WIBPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', WIBPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', WIBPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', WIBPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls
    urlpatterns += debug_toolbar_urls()
