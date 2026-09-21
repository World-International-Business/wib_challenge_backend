from django import forms

from .models import AcademicClass, Exam, Subject, TeacherQuestion, TeacherChoice


class TeacherChoiceForm(forms.Form):
    text = forms.CharField(label='Réponse', max_length=255, required=True)
    is_correct = forms.BooleanField(label='Réponse correcte', required=False)


class TeacherQuestionForm(forms.ModelForm):
    class Meta:
        model = TeacherQuestion
        fields = ['subject', 'title', 'description', 'question_type', 'points']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class StudentCreationForm(forms.Form):
    first_name = forms.CharField(label='Prénom', max_length=150)
    last_name = forms.CharField(label='Nom', max_length=150)
    email = forms.EmailField(label='Email')
    password = forms.CharField(label='Mot de passe initial', min_length=8, widget=forms.PasswordInput)
    academic_class = forms.ModelChoiceField(queryset=AcademicClass.objects.none(), label='Classe')
    student_number = forms.CharField(label='Matricule', max_length=80, required=False)


class ExamCreationForm(forms.ModelForm):
    starts_at = forms.DateTimeField(
        label='Début',
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
    )
    ends_at = forms.DateTimeField(
        label='Fin',
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
    )
    academic_class = forms.ModelChoiceField(queryset=AcademicClass.objects.none(), label='Classe')
    subject = forms.ModelChoiceField(queryset=Subject.objects.none(), label='Matière')

    class Meta:
        model = Exam
        fields = [
            'title', 'instructions', 'academic_class', 'subject', 'starts_at',
            'ends_at', 'duration_minutes', 'max_attempts', 'grading_scale',
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('starts_at') and cleaned.get('ends_at') and cleaned['ends_at'] <= cleaned['starts_at']:
            self.add_error('ends_at', 'La fin doit être postérieure au début.')
        return cleaned
