from django.contrib import admin
from django.core.exceptions import ValidationError

from challenges.models import Settings, Domain, Question, Choice, Challenge, Submission, Answer


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ['default_challenge_duration']
    fieldsets = (
        ('Paramètres', {
            'fields': ['default_challenge_duration']
        }),
    )

    def has_add_permission(self, request):
        return Settings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']
    ordering = ['name']
    fieldsets = (
        ('Domaine', {
            'fields': ['name', 'description']
        }),
    )

    def save_model(self, request, obj, form, change):
        if self.get_queryset(request).filter(name=obj.name.strip()).exists() and not change:
            raise ValidationError('Un domaine avec ce nom existe déjà')
        super().save_model(request, obj, form, change)


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['text', 'question', 'is_correct']
    search_fields = ['text']
    ordering = ['text']
    fieldsets = (
        ('Choix', {
            'fields': ['text', 'question', 'is_correct']
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.question.question_type == Question.QuestionType.OPEN_ANSWER:
            raise ValidationError('Une question de type "Réponse ouverte" ne peut pas avoir de choix')
        choices = obj.question.choices.all()
        choices = [choice for choice in choices if choice != obj] + [obj]
        print(any([choice.is_correct for choice in choices]))
        if not any([choice.is_correct for choice in choices]):
            raise ValidationError(
                f'La question {obj.question} doit avoir au moins un choix correct')

        super().save_model(request, obj, form, change)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['title', 'domain', 'question_type', 'level']
    search_fields = ['title']
    list_filter = ['level', 'question_type']
    ordering = ['title']
    inlines = [ChoiceInline]
    fieldsets = (
        ('Question', {
            'fields': ['title', 'description', 'domain', 'level', 'question_type']
        }),
    )

    @admin.display(description='Nombre de choix')
    def choices_count(self, obj):
        if obj.question_type == Question.QuestionType.MULTIPLE_CHOICE or obj.question_type == Question.QuestionType.UNIQUE_CHOICE:
            return obj.choices.count()
        return '-'

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        print(instances)
        print(form.instance.question_type)
        if form.instance.question_type == Question.QuestionType.OPEN_ANSWER:
            if len(instances) > 0:
                raise ValidationError('Une question de type "Réponse ouverte" ne peut pas avoir de choix')
        else:
            if len(instances) == 0:
                raise ValidationError(
                    'Une question de type "Choix multiple" ou "Choix unique" doit avoir au moins un choix')
            elif len([choice for choice in instances if choice.is_correct]) == 0:
                raise ValidationError(
                    'Une question de type "Choix multiple" ou "Choix unique" doit avoir au moins un choix correct')

        super().save_formset(request, form, formset, change)

    def save_model(self, request, obj, form, change):
        if change and obj.domain != form.initial['domain'] and obj.challenges.count() > 0:
            raise ValidationError(
                'Le domaine d\'une question ne peut pas être modifié, veillez supprimer les challenges associés ou retirer la question de ces challenges')
        super().save_model(request, obj, form, change)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'domain', 'duration']
    search_fields = ['title']
    readonly_fields = ['slug']
    ordering = ['title']
    fieldsets = (
        ('Challenge', {
            'fields': ['title', 'description', 'domain', 'duration', 'questions']
        }),
        ('Extras', {
            'fields': ['slug']
        }),
    )

    def save_form(self, request, form, change):
        # print(request, form.cleaned_data, change)
        questions = form.cleaned_data['questions']
        domain = form.cleaned_data['domain']
        if questions.count() == 0:
            raise ValidationError('Un challenge doit avoir au moins une question')
        if questions.filter(domain=domain).count() != questions.count():
            raise ValidationError(
                'Toutes les questions du challenge doivent appartenir au même domaine que celui du challenge')
        return super().save_form(request, form, change)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['submission', 'question', 'text', 'is_correct']
    search_fields = ['text']
    ordering = ['question__title']
    fieldsets = (
        ('Réponse', {
            'fields': ['question', 'submission', 'text', 'selected_choices']
        }),
    )

    def save_model(self, request, obj, form, change):
        self.check_answer(obj)
        super().save_model(request, obj, form, change)

    @classmethod
    def check_answer(cls, obj, choices=None):
        if choices is None:
            choices = obj.selected_choices.all()
        if obj.question.question_type == Question.QuestionType.OPEN_ANSWER and choices.count() > 0:
            raise ValidationError('Une question de type "Réponse ouverte" ne peut pas avoir de choix')
        if obj.question.question_type != Question.QuestionType.OPEN_ANSWER and obj.text != '':
            raise ValidationError('Une question de type "Choix multiple" ou "Choix unique" ne peut pas avoir de texte')
        if obj.question.question_type == Question.QuestionType.MULTIPLE_CHOICE and choices.count() == 0:
            raise ValidationError('Une question de type "Choix multiple" doit avoir au moins un choix sélectionné')
        if obj.question.question_type == Question.QuestionType.UNIQUE_CHOICE and choices.count() != 1:
            raise ValidationError('Une question de type "Choix unique" doit avoir exactement un choix sélectionné')


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1
    readonly_fields = ['is_correct']
    fields = ['question', 'selected_choices', 'text']

    def get_fields(self, request, obj=...):
        if obj is not None:
            return self.fields + ['is_correct']
        return self.fields

    def get_readonly_fields(self, request, obj=...):
        if obj is not None:
            return self.fields
        return super().get_readonly_fields(request, obj)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['challenge', 'get_candidate_email', 'result', 'submitted_at']
    search_fields = ['challenge__title', 'candidate_first_name', 'candidate_last_name', 'candidate_email']
    ordering = ['-submitted_at']
    readonly_fields = ['submitted_at']
    inlines = [AnswerInline]
    fieldsets = (
        ('Soumission', {
            'fields': ['challenge', 'candidate']
        }),
        ('Informations', {
            'fields': ['result', 'submitted_at'],
        }),
    )

    def get_candidate_email(self, obj):
        return obj.candidate.email if obj.candidate else ""

    get_candidate_email.admin_order_field = 'candidate__email'
    get_candidate_email.short_description = 'Candidate Email'

    def get_readonly_fields(self, request, obj=...):
        if obj is not None:
            return self.readonly_fields + ['challenge', 'candidate']
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        for answer in obj.answers.all():
            AnswerAdmin.check_answer(answer, answer.selected_choices.all())
