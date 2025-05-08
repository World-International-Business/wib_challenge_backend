from django.contrib import admin
from django.core.exceptions import ValidationError

from challenges.models import Settings, Challenge, Submission, Answer, APIUsage
from questions.models import Question


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = [f.name for f in Settings._meta.fields]
    fieldsets = (
        ('Paramètres', {
            'fields': ['default_challenge_duration']
        }),
    )

    def has_add_permission(self, request):
        return Settings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'domain', 'question_count', 'slug', 'duration']
    search_fields = ['title']
    readonly_fields = ['slug']
    ordering = ['title', 'id']
    fieldsets = (
        ('Challenge', {
            'fields': ['title', 'description', 'domain', 'duration', 'questions']
        }),
        ('Extras', {
            'fields': ['slug']
        }),
    )

    @admin.display(description='Nombre de questions', )
    def question_count(self, obj):
        return obj.questions.count()

    def save_form(self, request, form, change):
        # print(request, form.cleaned_data, change)
        questions = form.cleaned_data['questions']
        domain = form.cleaned_data['domain']
        if questions.count() == 0:
            raise ValidationError('Un challenge doit avoir au moins une question')
        # if questions.filter(domain=domain).count() != questions.count():
        #     raise ValidationError(
        #         'Toutes les questions du challenge doivent appartenir au même domaine que celui du challenge')
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
    search_fields = ['challenge__title', 'candidate__first_name', 'candidate__last_name', 'candidate__email']
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


@admin.register(APIUsage)
class APIUsageAdmin(admin.ModelAdmin):
    list_display = ('date', 'count')
    list_display_links = ('date',)
