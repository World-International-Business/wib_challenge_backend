import json
from pathlib import Path
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import render

from questions.models import Question


class JSONInputForm(forms.Form):
    json = forms.CharField(widget=forms.Textarea, label='Enter JSON Data')


@login_required
@permission_required('questions.add_question', raise_exception=True)
def json_input(request, question_category=Question.QuestionCategory.NORMAL):
    n = None
    if request.method == 'POST':
        form = JSONInputForm(request.POST)
        if form.is_valid():
            json_data = form.cleaned_data['json']
            n = process_json(json_data, question_category.upper())
    else:
        form = JSONInputForm()
    return render(request, 'json_input.html', {'form': form, 'n': n, 'question_category': question_category})


def process_json(json_data, question_category: str):
    try:
        data = json.loads(json_data)
        tag: str = data.get("tags", [])[0]
        question_type = data.get("questions", [])[0]['question_type']
        file_name = f"{tag.replace(' ', '_')}_{question_type}.json".lower()
        file_name = Path(tempfile.mkdtemp()) / file_name

        with open(file_name, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))

        call_command('import_questions', str(file_name),
                     category=question_category.upper(), data_dir=settings.BASE_DIR / 'data')
        call_command('create_default_questions', data_dir=settings.BASE_DIR / 'data', force=True)
        # Clean up the temporary file
        file_name.unlink(missing_ok=True)
        # Return the number of questions imported
        return len(data.get("questions", []))

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
