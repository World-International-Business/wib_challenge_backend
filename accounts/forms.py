# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Adresse Email")
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    # experience_level = forms.ChoiceField(choices=User.ExperienceLevel.choices, required=False,label="Niveau d'expérience")
    # experience = forms.IntegerField(min_value=0, required=False, label="Année dexpérience")

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
    experience_level = forms.ChoiceField(choices=User.ExperienceLevel.choices, required=False, label="Niveau d'expérience")
    experience = forms.IntegerField(min_value=0, required=False, label="Années d'expérience")

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'experience_level', 'experience']

    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})