from django.contrib import admin
from django.core.exceptions import ValidationError

from questions.models import Domain, Choice, Question


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['name', ]
    search_fields = ['name']
    ordering = ['name']
    fieldsets = (
        ('Domaine', {
            'fields': ['name', ]
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
    list_display = ['title', 'question_type', 'level', 'created_at']
    search_fields = ['title']
    list_filter = ['level', 'question_type']
    ordering = ['title']
    inlines = [ChoiceInline]
    fieldsets = (
        ('Question', {
            'fields': ['title', 'description', 'tags', 'level', 'question_type']
        }),
    )

    @admin.display(description='Nombre de choix')
    def choices_count(self, obj):
        if obj.question_type == Question.QuestionType.MULTIPLE_CHOICE or obj.question_type == Question.QuestionType.UNIQUE_CHOICE:
            return obj.choices.count()
        return '-'

        # def save_formset(self, request, form, formset, change):
        #     instances = formset.save(commit=False)
        #     print(instances)
        #     print(form.instance.question_type)
        #     if form.instance.question_type == Question.QuestionType.OPEN_ANSWER:
        #         if len(instances) > 0:
        #             raise ValidationError('Une question de type "Réponse ouverte" ne peut pas avoir de choix')
        #     else:
        #         if len(instances) == 0:
        #             raise ValidationError(
        #                 'Une question de type "Choix multiple" ou "Choix unique" doit avoir au moins un choix')
        #         elif len([choice for choice in instances if choice.is_correct]) == 0:
        #             raise ValidationError(
        #                 'Une question de type "Choix multiple" ou "Choix unique" doit avoir au moins un choix correct')

        super().save_formset(request, form, formset, change)

    # def save_model(self, request, obj, form, change):
    # if change and obj.domain != form.initial['domain'] and obj.challenges.count() > 0:
    #     raise ValidationError(
    #         'Le domaine d\'une question ne peut pas être modifié, veillez supprimer les challenges associés ou retirer la question de ces challenges')
    # super().save_model(request, obj, form, change)
