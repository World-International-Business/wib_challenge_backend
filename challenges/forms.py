from datetime import timedelta

from django import forms
from django.forms import inlineformset_factory

from challenges.models import TestDurationProfile
from questions.models import Category, Choice, Criteria, Domain, Question, Tag
from wib_challenge.enums import ExperienceLevel


class HHMMSSDurationField(forms.DurationField):
    """Durée au format HH:MM:SS avec un texte d'aide."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('help_text', 'Format HH:MM:SS (ex: 00:30:00)')
        super().__init__(*args, **kwargs)
        self.widget.attrs.update({'placeholder': 'HH:MM:SS'})

    def prepare_value(self, value):
        if isinstance(value, timedelta):
            total = int(value.total_seconds())
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            return f'{h:02d}:{m:02d}:{s:02d}'
        return value


class TestDurationProfileForm(forms.ModelForm):
    technical_duration = HHMMSSDurationField(label='Durée test technique')
    logical_duration = HHMMSSDurationField(label='Durée test psychotechnique')
    personality_duration = HHMMSSDurationField(label='Durée test de personnalité')

    class Meta:
        model = TestDurationProfile
        fields = ['domain', 'experience_level', 'technical_duration', 'logical_duration', 'personality_duration']
        widgets = {
            'domain': forms.Select(attrs={'class': 'form-select'}),
            'experience_level': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned = super().clean()
        for field in ['technical_duration', 'logical_duration', 'personality_duration']:
            value = cleaned.get(field)
            if value and value.total_seconds() <= 0:
                self.add_error(field, 'La durée doit être positive.')
        return cleaned


class DomainForm(forms.ModelForm):
    class Meta:
        model = Domain
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du profil'}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'domain']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la catégorie'}),
            'domain': forms.Select(attrs={'class': 'form-select'}),
        }


class CriteriaForm(forms.ModelForm):
    class Meta:
        model = Criteria
        fields = ['name', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du critère'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'criteria']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la compétence'}),
            'criteria': forms.Select(attrs={'class': 'form-select'}),
        }


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['category', 'tags', 'title', 'description', 'level', 'question_type', 'question_category']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'question_category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['level'].choices = ExperienceLevel.choices
        self.fields['question_type'].choices = Question.QuestionType.choices
        self.fields['question_category'].choices = Question.QuestionCategory.choices


ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    fields=['text', 'is_correct'],
    extra=4,
    can_delete=True,
    widgets={
        'text': forms.TextInput(attrs={'class': 'form-control'}),
        'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    },
    labels={
        'text': 'Texte du choix',
        'is_correct': 'Correct',
    }
)
