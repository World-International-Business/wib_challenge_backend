from django import forms
from django.contrib.auth.forms import UserCreationForm
from django_select2.forms import Select2MultipleWidget
from django.forms import inlineformset_factory

from wib_challenge.enums import ExperienceLevel
from .models import User, UserSkill
from questions.models import Tag


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Adresse Email")
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")


    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

# Formulaire de mise à jour du profil
class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Adresse Email")
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    experience_level = forms.ChoiceField(choices=ExperienceLevel.choices, required=False, label="Niveau d'expérience")
    experience = forms.IntegerField(min_value=0, required=False, label="Années d'expérience")

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'experience_level', 'experience']

    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class UserSkillForm(forms.ModelForm):
    class Meta:
        model = UserSkill
        fields = ['skill', 'experience_level']
        labels = {
            'skill': 'Compétence',
            'experience_level': 'Niveau d\'expérience',
        }
        widgets = {
            'skill': forms.Select(attrs={'class': 'form-control'}),
            'experience_level': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        skill = cleaned_data.get('skill')
        user = self.instance.user if self.instance else None

        if skill and user:
            # Vérifie si la compétence existe déjà pour cet utilisateur
            if UserSkill.objects.filter(user=user, skill=skill).exists():
                raise forms.ValidationError("Un objet User skill avec ces champs User et Skill existe déjà.")
        return cleaned_data

UserSkillFormSet = inlineformset_factory(User, UserSkill, form=UserSkillForm, extra=0)
