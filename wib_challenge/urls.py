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

from debug_toolbar.toolbar import debug_toolbar_urls
from django.contrib import admin
from django.urls import path

from accounts.views import login_view, register_view, logout_view, update_profile
from challenges.views import home_view, evaluation_results, challenge_evaluation_view, submit_evaluation_view, \
    generate_challenge, generate_logical_challenge, generate_personality_challenge, personality_details_view, \
    personality_evaluation_view
from questions.models import Question
from wib_challenge.views import json_input

urlpatterns = [
    path('admin/', admin.site.urls),
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
]
urlpatterns += debug_toolbar_urls()
