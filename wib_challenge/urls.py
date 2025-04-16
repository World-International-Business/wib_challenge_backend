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
import json

from debug_toolbar.toolbar import debug_toolbar_urls
# from debug_toolbar.urls import debug_toolbar_urls
from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path

from accounts.views import login_view, register_view, logout_view, update_profile
from challenges.views import home_view, evaluation_results, challenge_evaluation_view, submit_evaluation_view


# Define the form
class JSONInputForm(forms.Form):
    jsondata = forms.CharField(widget=forms.Textarea, label='Enter JSON Data')


# Define the view
def json_input(request):
    n = None
    if request.method == 'POST':
        form = JSONInputForm(request.POST)
        if form.is_valid():
            json_data = form.cleaned_data['jsondata']
            n = process_json(json_data)
    else:
        form = JSONInputForm()
    return render(request, 'json_input.html', {'form': form, 'n': n})


def process_json(json_data):
    try:
        data = json.loads(json_data)
        tag: str = data.get("tags", [])[0]
        question_type = data.get("questions", [])[0]['question_type']
        file_name = f"{tag.replace(' ', '_')}_{question_type}.json".lower()
        file_name = settings.BASE_DIR / 'data' / file_name
        file_name.parent.mkdir(parents=True, exist_ok=True)
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))

        call_command('create_default_questions', data_dir=file_name.parent)
        return len(data.get("questions", []))

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),

    path('resultats/', evaluation_results, name='results'),
    path('resultats/<int:submission_id>-<slug:slug>-<int:challenge_id>', evaluation_results, name='result-detail'),
    # URLs d'authentification

    path('evaluation/', challenge_evaluation_view, name='challenge_evaluation'),
    path('evaluation/<slug:slug>-<int:challenge_id>', challenge_evaluation_view, name='challenge_evaluation_detail'),
    path('submit_evaluation/', submit_evaluation_view, name='submit_evaluation'),

    # URLs d'authentification
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('profile/update/', update_profile, name='update_profile'),
    # path('accounts/', include('allauth.urls')),  # Django Allauth URLs
    path('____', json_input, name='json_input'),
]
urlpatterns += debug_toolbar_urls()
