import json

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import render


class JSONInputForm(forms.Form):
    json = forms.CharField(widget=forms.Textarea, label='Enter JSON Data')


@login_required
@permission_required('questions.add_question', raise_exception=True)
def json_input(request):
    n = None
    if request.method == 'POST':
        form = JSONInputForm(request.POST)
        if form.is_valid():
            json_data = form.cleaned_data['json']
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
