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
from django.urls import path, include

from accounts.views import login_view, register_view, logout_view, update_profile
from challenges.views import (
    challenge_evaluation_view, submit_evaluation_view
)
from challenges.views import evaluation_results, home_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),

    path('resultats/', evaluation_results, name='resultats'),
    path('resultats/<int:submission_id>-<slug:slug>-<int:challenge_id>', evaluation_results, name='resultat-detail'),
    # URLs d'authentification

    path('evaluation/', challenge_evaluation_view, name='challenge_evaluation'),
    path('evaluation/<slug:slug>-<int:challenge_id>', challenge_evaluation_view, name='challenge_evaluation_detail'),
    path('submit_evaluation/', submit_evaluation_view, name='submit_evaluation'),

    # URLs d'authentification
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('profile/update/', update_profile, name='update_profile'),
    path('accounts/', include('allauth.urls')),  # Django Allauth URLs

]

urlpatterns += debug_toolbar_urls()
