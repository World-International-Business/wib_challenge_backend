from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count

from challenges.models import Settings, Challenge, Submission, Answer, APIUsage, PersonalityChallenge, PersonalityAnswer
from questions.models import Question, Tag


class TagFilter(admin.SimpleListFilter):
    title = 'Tags'
    parameter_name = 'tag'

    def lookups(self, request, model_admin):
        tags = Tag.objects.annotate(
            num_challenges=Count('challenges')
        ).filter(num_challenges__gt=0).order_by('name')
        return [(tag.id, tag.name) for tag in tags]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(challenge__questions__tags__id=self.value()).distinct()
        return queryset


class LogicalTestFilter(admin.SimpleListFilter):
    title = 'Test logique'
    parameter_name = 'is_logical'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Oui'),
            ('0', 'Non'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(challenge__is_logical=True)
        if self.value() == '0':
            return queryset.filter(challenge__is_logical=False)
        return queryset


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
    list_display = ['id', 'title', 'domain', 'question_count', 'get_tags', 'slug', 'duration', 'is_logical', 'is_active']
    search_fields = ['title', 'description', 'questions__tags__name']
    list_filter = ['domain', 'is_active', 'is_logical', 'questions__tags']
    readonly_fields = ['slug']
    ordering = ['title', 'id']
    fieldsets = (
        ('Challenge', {
            'fields': ['title', 'description', 'domain', 'duration', 'questions', 'is_logical']
        }),
        ('Statut', {
            'fields': ['is_active']
        }),
        ('Extras', {
            'fields': ['slug']
        }),
    )

    @admin.display(description='Nombre de questions', )
    def question_count(self, obj):
        return obj.questions.count()

    @admin.display(description='Tags')
    def get_tags(self, obj):
        tags = set()
        for question in obj.questions.all():
            for tag in question.tags.all():
                tags.add(tag.name)
        return ", ".join(sorted(tags)) if tags else "-"

    def save_form(self, request, form, change):
        questions = form.cleaned_data['questions']
        domain = form.cleaned_data['domain']
        if questions.count() == 0:
            raise ValidationError('Un challenge doit avoir au moins une question')
        return super().save_form(request, form, change)


class PersonalityAnswerInline(admin.TabularInline):
    model = PersonalityAnswer
    extra = 1
    fields = ['question', 'selected_choices', 'text', 'answered_at']
    readonly_fields = ['answered_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.corrected:
            return ['question', 'selected_choices', 'text', 'answered_at']
        return ['answered_at']


@admin.register(PersonalityChallenge)
class PersonalityChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_candidate_email', 'is_passed', 'corrected']
    search_fields = ['title', 'candidate__first_name', 'candidate__last_name', 'candidate__email']
    list_filter = ['is_passed', 'corrected']
    readonly_fields = ['slug', 'personality_detail']
    inlines = [PersonalityAnswerInline]
    fieldsets = (
        ('Challenge', {
            'fields': ['title', 'description', 'candidate', 'questions']
        }),
        ('Statut', {
            'fields': ['is_passed', 'corrected']
        }),
        ('Analyse de personnalité', {
            'fields': ['personality_detail'],
            'classes': ['collapse']
        }),
        ('Extras', {
            'fields': ['slug']
        }),
    )

    def get_candidate_email(self, obj):
        return obj.candidate.email if obj.candidate else ""

    get_candidate_email.admin_order_field = 'candidate__email'
    get_candidate_email.short_description = 'Candidat Email'
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.corrected:
            return self.readonly_fields + ['title', 'description', 'candidate', 'questions', 'is_passed']
        return self.readonly_fields


@admin.register(PersonalityAnswer)
class PersonalityAnswerAdmin(admin.ModelAdmin):
    list_display = ['submission', 'question', 'text', 'answered_at']
    search_fields = ['text', 'question__title', 'submission__candidate__email']
    list_filter = ['answered_at']
    ordering = ['-answered_at']
    fieldsets = (
        ('Réponse', {
            'fields': ['question', 'submission', 'text', 'selected_choices']
        }),
        ('Métadonnées', {
            'fields': ['answered_at']
        }),
    )
    readonly_fields = ['answered_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.submission.corrected:
            return ['question', 'submission', 'text', 'selected_choices', 'answered_at']
        return ['answered_at']


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['submission', 'question', 'text', 'is_correct']
    search_fields = ['text', 'question__title', 'submission__candidate__email']
    list_filter = ['is_correct', 'answered_at']
    ordering = ['question__title']
    fieldsets = (
        ('Réponse', {
            'fields': ['question', 'submission', 'text', 'selected_choices', 'is_correct']
        }),
        ('Métadonnées', {
            'fields': ['answered_at']
        }),
    )
    readonly_fields = ['answered_at']

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
    fields = ['question', 'selected_choices', 'text', 'is_correct', 'answered_at']
    readonly_fields = ['is_correct', 'answered_at']

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_corrected:
            return ['question', 'selected_choices', 'text', 'is_correct', 'answered_at']
        return ['is_correct', 'answered_at']


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['challenge', 'get_candidate_email', 'get_challenge_tags', 'is_logical_test', 'result_percent_display', 'status', 'submitted_at']
    search_fields = ['challenge__title', 'candidate__first_name', 'candidate__last_name', 'candidate__email', 'challenge__questions__tags__name']
    list_filter = ['status', 'submitted_at', LogicalTestFilter, TagFilter]
    ordering = ['-submitted_at']
    readonly_fields = ['submitted_at', 'result', 'get_challenge_tags', 'is_logical_test']
    inlines = [AnswerInline]
    fieldsets = (
        ('Soumission', {
            'fields': ['challenge', 'candidate']
        }),
        ('Statut', {
            'fields': ['status']
        }),
        ('Tags', {
            'fields': ['get_challenge_tags', 'is_logical_test'],
            'classes': ['collapse']
        }),
        ('Résultats', {
            'fields': ['result', 'submitted_at'],
        }),
    )

    def get_candidate_email(self, obj):
        return obj.candidate.email if obj.candidate else ""
    
    @admin.display(description='Tags du Challenge')
    def get_challenge_tags(self, obj):
        if not obj.challenge:
            return "-"
        
        tags = set()
        for question in obj.challenge.questions.all():
            for tag in question.tags.all():
                tags.add(tag.name)
        return ", ".join(sorted(tags)) if tags else "-"
    
    @admin.display(description='Test logique')
    def is_logical_test(self, obj):
        if obj.challenge and obj.challenge.is_logical:
            return "Oui"
        return "Non"
    
    @admin.display(description='Résultat (%)')
    def result_percent_display(self, obj):
        if obj.result is not None:
            return f"{obj.result_percent:.1f}%"
        return "Non corrigé"

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_corrected:
            return self.readonly_fields + ['challenge', 'candidate', 'status']
        return self.readonly_fields


@admin.register(APIUsage)
class APIUsageAdmin(admin.ModelAdmin):
    list_display = ('date', 'count', 'limit_reached')
    list_display_links = ('date',)
    list_filter = ['date']
    readonly_fields = ['limit_reached']
    
    @admin.display(description='Limite atteinte')
    def limit_reached(self, obj):
        return "Oui" if obj.limit_reached else "Non"

