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

from accounts.views import (login_view, register_view, verify_email_view, logout_view, update_profile,
                           student_profile_view, school_staff_profile_view, candidate_profile_view,
                           WIBPasswordResetView, WIBPasswordResetDoneView,
                           WIBPasswordResetConfirmView, WIBPasswordResetCompleteView)
from challenges.views import (
     home_view, evaluation_results, challenge_evaluation_view, submit_evaluation_view,
     generate_challenge, generate_logical_challenge, generate_personality_challenge,
     personality_details_view, personality_evaluation_view, candidate_list_view,
     candidate_detail_view, candidate_retake_view, candidate_invitation_view,
     candidate_message_view, recruitment_campaign_access_view,
     recruitment_campaign_list_view, recruitment_campaign_detail_view,
     manual_correct_submission_view, manual_correct_personality_view,
     leaderboard_view, admin_dashboard_view,
)
from questions.models import Question
from wib_challenge.views import json_input
from education.views import (
     school_home_view, school_dashboard_view, school_student_create_view,
     school_exam_create_view, school_exam_publish_view, student_dashboard_view,
     school_exam_results_publish_view, school_exam_attempt_view, school_exam_integrity_event_view,
     school_attempt_grade_view, teacher_question_list_view, teacher_question_create_view,
     teacher_question_update_view, teacher_question_delete_view,
)
from challenges.admin_views import (
    duration_profile_list_view, duration_profile_create_view,
    duration_profile_update_view, duration_profile_delete_view,
    profile_manager_view, question_list_view, question_create_view,
    question_update_view, question_delete_view,
)

urlpatterns = [
    # Gestion admin personnalisée (doit être avant le catch-all de l'admin Django)
    path('admin/durees/', duration_profile_list_view, name='duration_profile_list'),
    path('admin/durees/ajouter/', duration_profile_create_view, name='duration_profile_create'),
    path('admin/durees/<int:pk>/modifier/', duration_profile_update_view, name='duration_profile_update'),
    path('admin/durees/<int:pk>/supprimer/', duration_profile_delete_view, name='duration_profile_delete'),
    path('admin/profils/', profile_manager_view, name='profile_manager'),
    path('admin/questions/', question_list_view, name='question_list'),
    path('admin/questions/ajouter/', question_create_view, name='question_create'),
    path('admin/questions/<int:pk>/modifier/', question_update_view, name='question_update'),
    path('admin/questions/<int:pk>/supprimer/', question_delete_view, name='question_delete'),

    path('admin/', admin.site.urls),
     path('ecole/', school_home_view, name='school_home'),
     path('ecole/tableau-de-bord/', school_dashboard_view, name='school_dashboard'),
     path('ecole/eleves/ajouter/', school_student_create_view, name='school_student_create'),
     path('ecole/questions/', teacher_question_list_view, name='teacher_question_list'),
     path('ecole/questions/ajouter/', teacher_question_create_view, name='teacher_question_create'),
     path('ecole/questions/<int:question_id>/modifier/', teacher_question_update_view, name='teacher_question_update'),
     path('ecole/questions/<int:question_id>/supprimer/', teacher_question_delete_view, name='teacher_question_delete'),
     path('ecole/epreuves/ajouter/', school_exam_create_view, name='school_exam_create'),
     path('ecole/epreuves/<int:exam_id>/publier/', school_exam_publish_view, name='school_exam_publish'),
     path('ecole/epreuves/<int:exam_id>/publier-resultats/', school_exam_results_publish_view, name='school_exam_results_publish'),
     path('ecole/epreuves/<int:exam_id>/composer/', school_exam_attempt_view, name='school_exam_attempt'),
     path('ecole/tentatives/<int:attempt_id>/integrite/', school_exam_integrity_event_view, name='school_exam_integrity_event'),
     path('ecole/tentatives/<int:attempt_id>/corriger/', school_attempt_grade_view, name='school_attempt_grade'),
     path('ecole/mes-epreuves/', student_dashboard_view, name='student_dashboard'),
    path('tableau-de-bord/', admin_dashboard_view, name='admin_dashboard'),
     path('recrutement/campagnes/', recruitment_campaign_list_view, name='recruitment_campaign_list'),
     path('recrutement/campagnes/<int:campaign_id>/', recruitment_campaign_detail_view, name='recruitment_campaign_detail'),
     path('recrutement/campagnes/<int:campaign_id>/acces/', recruitment_campaign_access_view, name='recruitment_campaign_access'),

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
     path('register/verify/', verify_email_view, name='verify_email'),
    path('logout/', logout_view, name='logout'),
    path('profile/update/', update_profile, name='update_profile'),
    path('profile/eleve/', student_profile_view, name='student_profile'),
    path('profile/enseignant/', school_staff_profile_view, name='school_staff_profile'),
    path('profile/candidat/', candidate_profile_view, name='candidate_profile'),
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
    path('candidats/', candidate_list_view, name='candidate_list'),
    path('candidat/<int:user_id>/', candidate_detail_view, name='candidate_detail'),
    path('candidat/<int:user_id>/retake/', candidate_retake_view, name='candidate_retake'),
     path('candidat/<int:user_id>/invitation/', candidate_invitation_view, name='candidate_invitation'),
     path('candidat/<int:user_id>/message/', candidate_message_view, name='candidate_message'),
    path('correction/submission/<int:submission_id>/', manual_correct_submission_view,
         name='manual_correct_submission'),
    path('correction/personality/<int:personality_id>/', manual_correct_personality_view,
         name='manual_correct_personality'),
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
