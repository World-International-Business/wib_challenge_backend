from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from django.db.models import F
from django.forms import inlineformset_factory

from questions.models import Domain, Question, Tag
from wib_challenge.enums import ExperienceLevel
from .models import User, UserSkill


class DomainSkillSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value and hasattr(value, 'instance') and value.instance:
            try:
                domain = getattr(
                    value.instance, 'domain_name', None)
                if not domain:
                    domain = value.instance.criteria.category.domain.name
                option['attrs']['data-domain'] = domain
            except Exception:
                pass
        return option


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
    experience_level = forms.ChoiceField(
        choices=ExperienceLevel.choices, required=False, label="Niveau d'expérience")
    experience = forms.IntegerField(
        min_value=0, required=False, label="Années d'expérience")
    domain = forms.ModelChoiceField(
        # Affiche tous les profils/domaines disponibles
        queryset=Domain.objects.order_by('name'),
        required=False,
        empty_label="Sélectionner un domaine",
        label="Domaine"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email',
                  'experience_level', 'experience', 'domain']

    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

    def clean_domain(self):
        domain = self.cleaned_data['domain']
        if not domain:
            raise forms.ValidationError("Veuillez sélectionner un domaine.")
        return domain


class UserSkillForm(forms.ModelForm):
    skill = forms.ModelChoiceField(
        queryset=Tag.objects.none(),
        required=True,
        empty_label="Sélectionner une compétence",
        label="Compétence"
    )

    class Meta:
        model = UserSkill
        fields = ['skill', 'experience_level']
        labels = {
            'skill': 'Compétence',
            'experience_level': 'Niveau d\'expérience',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Tag.objects.annotate(
            domain_name=F('criteria__category__domain__name')
        ).distinct().order_by('domain_name', 'name')
        self.fields['skill'].queryset = qs
        self.fields['skill'].widget = DomainSkillSelect(attrs={'class': 'form-control skill-select'})
        self.fields['skill'].widget.choices = self.fields['skill'].choices
        self.fields['experience_level'].widget.attrs.update({'class': 'form-control'})


class WIBPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        required=True,
        label="Adresse Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrez votre adresse email'
        })
    )


class WIBSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrez votre nouveau mot de passe'
        }),
        strip=False,
    )
    new_password2 = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmez votre nouveau mot de passe'
        }),
        strip=False,
    )


UserSkillFormSet = inlineformset_factory(
    User, UserSkill, form=UserSkillForm, extra=1, fk_name='user')
