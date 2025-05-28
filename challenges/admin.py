from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils.html import format_html

from challenges.models import (Settings, Challenge, SubmissionAttempt, Submission, Answer, APIUsage,
                               PersonalityChallenge, PersonalityAnswer)
from questions.models import Tag


class TagFilter(admin.SimpleListFilter):
    title = 'Tags'
    parameter_name = 'tag'

    def lookups(self, request, model_admin):
        tags = Tag.objects.annotate(num_challenges=Count('challenges')).filter(num_challenges__gt=0).order_by('name')
        return [(tag.id, tag.name) for tag in tags]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(challenge__questions__tags__id=self.value()).distinct()
        return queryset


class LogicalTestFilter(admin.SimpleListFilter):
    title = 'Test logique'
    parameter_name = 'is_logical'

    def lookups(self, request, model_admin):
        return (('1', 'Oui'), ('0', 'Non'),)

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(challenge__is_logical=True)
        if self.value() == '0':
            return queryset.filter(challenge__is_logical=False)
        return queryset


class QuestionStatusFilter(admin.SimpleListFilter):
    title = 'Statut des questions'
    parameter_name = 'question_status'

    def lookups(self, request, model_admin):
        return (('empty', 'Sans questions'), ('with_questions', 'Avec questions'),)

    def queryset(self, request, queryset):
        if self.value() == 'empty':
            return queryset.annotate(question_count=Count('questions')).filter(question_count=0)
        if self.value() == 'with_questions':
            return queryset.annotate(question_count=Count('questions')).filter(question_count__gt=0)
        return queryset


class ExperienceLevelFilter(admin.SimpleListFilter):
    title = 'Niveau d\'expérience'
    parameter_name = 'experience_level'

    def lookups(self, request, model_admin):
        return (('1', 'Débutant'), ('2', 'Intermédiaire'), ('3', 'Avancé'),)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(questions__level=self.value()).distinct()
        return queryset


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'default_challenge_duration', 'is_database_already_populated']

    fieldsets = (('Durées des challenges', {
        'fields': ('default_challenge_duration', 'beginner_challenge_duration', 'intermediate_challenge_duration',
                   'advanced_challenge_duration'), 'classes': ('wide',), }), ('Configuration des questions', {
        'fields': ('open_answer_question_count_per_tag', 'multiple_choice_question_count_per_tag',
                   'unique_choice_question_count_per_tag'), }),
                 ('Base de données', {'fields': ('is_database_already_populated',), }),)

    def has_add_permission(self, request):
        return Settings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


class ChallengeQuestionInline(admin.TabularInline):
    model = Challenge.questions.through
    extra = 1
    verbose_name = "Question"
    verbose_name_plural = "Questions"
    autocomplete_fields = ['question']


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'domain', 'duration_display', 'question_count', 'get_tags', 'submissions_count',
                    'is_logical', 'is_active']
    search_fields = ['title', 'description', 'domain__name', 'questions__tags__name']
    list_filter = ['domain', 'is_active', 'is_logical', QuestionStatusFilter, ExperienceLevelFilter]
    readonly_fields = ['slug', 'submissions_count', 'success_rate']
    autocomplete_fields = ['domain']
    filter_horizontal = ['questions']
    inlines = [ChallengeQuestionInline]

    fieldsets = (('Informations de base', {'fields': ('title', 'description', 'domain', 'duration')}),
                 ('Configuration', {'fields': ('is_logical', 'is_active'), }), ('Questions', {'fields': ('questions',),
            'description': 'Sélectionnez les questions à inclure dans ce challenge', }),
                 ('Statistiques', {'fields': ('submissions_count', 'success_rate'), 'classes': ('collapse',), }),
                 ('Extras', {'fields': ('slug',), 'classes': ('collapse',), }),)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('domain').prefetch_related('questions',
                                                                                       'questions__tags').annotate(
            submission_count=Count('submissions', distinct=True))

    @admin.display(description='Durée', ordering='duration')
    def duration_display(self, obj):
        total_seconds = int(obj.duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @admin.display(description='Nombre de questions', ordering='question_count')
    def question_count(self, obj):
        return obj.questions.count()

    @admin.display(description='Tags')
    def get_tags(self, obj):
        tags = set()
        for question in obj.questions.all():
            for tag in question.tags.all():
                tags.add(tag.name)
        return ", ".join(sorted(tags)[:5]) + ("..." if len(tags) > 5 else "") if tags else "-"

    @admin.display(description='Soumissions', ordering='submission_count')
    def submissions_count(self, obj):
        return getattr(obj, 'submission_count', obj.submissions.count())

    @admin.display(description='Taux de réussite (%)')
    def success_rate(self, obj):
        submissions = obj.submissions.filter(status=Submission.CorrectionStatus.CORRECTED)
        if submissions.exists():
            success_count = submissions.filter(result__gte=0.5).count()
            rate = (success_count / submissions.count()) * 100
            return f"{rate:.1f}% ({success_count}/{submissions.count()})"
        return "Aucune soumission corrigée"

    def save_form(self, request, form, change):
        if 'questions' in form.cleaned_data and not form.cleaned_data['questions'].exists():
            raise ValidationError('Un challenge doit avoir au moins une question')
        return super().save_form(request, form, change)


@admin.register(SubmissionAttempt)
class SubmissionAttemptAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'challenge', 'started_at', 'ended_at', 'is_finished_display', 'performance_display',
                    'remaining_time_display']
    list_filter = ['started_at', 'ended_at', 'challenge', 'candidate']
    search_fields = ['candidate__email', 'candidate__first_name', 'candidate__last_name', 'challenge__title']
    autocomplete_fields = ['candidate', 'challenge', 'submission']
    readonly_fields = ['started_at', 'ended_at', 'performance_display', 'remaining_time_display', 'questions_count',
                       'is_finished_display']

    fieldsets = (('Informations de base', {'fields': ('candidate', 'challenge', 'submission')}),
                 ('Informations temporelles',
                  {'fields': ('started_at', 'ended_at', 'is_finished_display', 'remaining_time_display'), }),
                 ('Performance', {'fields': ('performance_display', 'questions_count'), 'classes': ('collapse',), }),)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('candidate', 'challenge', 'submission')

    @admin.display(description='Terminé', boolean=True)
    def is_finished_display(self, obj):
        return obj.is_finished

    @admin.display(description='Performance')
    def performance_display(self, obj):
        if obj.performance:
            perf_seconds = int(obj.performance.total_seconds())
            hours = perf_seconds // 3600
            minutes = (perf_seconds % 3600) // 60
            seconds = perf_seconds % 60

            if obj.performance_percent > 80:
                color = "green"
            elif obj.performance_percent > 50:
                color = "orange"
            else:
                color = "red"
            time_str = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
            percent = f'{obj.performance_percent:.1f}%'
            return format_html('<span style="color: {};">{} ({})</span>', color, time_str, percent)
        return "-"

    @admin.display(description='Temps restant')
    def remaining_time_display(self, obj):
        if not obj.is_finished:
            remaining = obj.remaining_time
            if remaining.total_seconds() > 0:
                remaining_seconds = int(remaining.total_seconds())
                hours = remaining_seconds // 3600
                minutes = (remaining_seconds % 3600) // 60
                seconds = remaining_seconds % 60

                if remaining.total_seconds() < 300:
                    color = "red"
                elif remaining.total_seconds() < 900:
                    color = "orange"
                else:
                    color = "green"

                return format_html('<span style="color: {};">{:02d}:{:02d}:{:02d}</span>', color, hours, minutes,
                    seconds)
            return format_html('<span style="color: red;">Expiré</span>')
        return "Terminé"

    @admin.display(description='Questions')
    def questions_count(self, obj):
        if obj.challenge:
            return obj.challenge.questions.count()
        return 0


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ['question', 'text', 'selected_choices_display', 'is_correct', 'answered_at', 'score_display']
    can_delete = False
    fields = ['question', 'text', 'selected_choices_display', 'is_correct', 'score_display', 'answered_at']

    def selected_choices_display(self, obj):
        choices = obj.selected_choices.all()
        if not choices:
            return obj.text or "-"
        return ", ".join([choice.text for choice in choices])

    def score_display(self, obj):
        if obj.is_correct is not None:
            score = obj.average_score * 100
            if score >= 80:
                color = "green"
            elif score >= 50:
                color = "orange"
            else:
                color = "red"
            return format_html('<span style="color: {};">{}</span>', color, f'{score:.1f}%')
        return "-"

    score_display.short_description = "Score"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['candidate_display', 'challenge', 'get_challenge_tags', 'status_display', 'result_percent_display',
                    'correct_answers_display', 'submitted_at']
    search_fields = ['candidate__email', 'candidate__first_name', 'candidate__last_name', 'challenge__title',
                     'challenge__questions__tags__name']
    list_filter = ['status', 'submitted_at', LogicalTestFilter, TagFilter, 'challenge', 'candidate']
    ordering = ['-submitted_at']
    readonly_fields = ['submitted_at', 'result', 'get_challenge_tags', 'is_logical_test', 'answers_count',
                       'correct_answers_count', 'attempt_duration']
    inlines = [AnswerInline]
    autocomplete_fields = ['candidate', 'challenge']

    fieldsets = (('Informations de base', {'fields': ('candidate', 'challenge', 'status')}),
                 ('Résultats', {'fields': ('result', 'correct_answers_count', 'answers_count', 'submitted_at'), }),
                 ('Informations du challenge', {'fields': ('get_challenge_tags', 'is_logical_test', 'attempt_duration'),
                     'classes': ('collapse',), }),)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('candidate', 'challenge', 'attempt').prefetch_related(
            'answers', 'challenge__questions', 'challenge__questions__tags').annotate(answer_count=Count('answers'),
            correct_answer_count=Count('answers', filter={'answers__is_correct': True}))

    @admin.display(description='Candidat', ordering='candidate__email')
    def candidate_display(self, obj):
        if not obj.candidate:
            return "-"
        return format_html('{} ({})', obj.candidate.email, obj.candidate.get_full_name() or 'Sans nom')

    @admin.display(description='Statut', ordering='status')
    def status_display(self, obj):
        if obj.status == Submission.CorrectionStatus.PENDING:
            return format_html('<span style="color: orange;">En attente</span>')
        return format_html('<span style="color: green;">Corrigé</span>')

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

    @admin.display(description='Résultat (%)', ordering='result')
    def result_percent_display(self, obj):
        if obj.result is not None:
            score = obj.result_percent
            if score >= 80:
                color = "green"
            elif score >= 50:
                color = "orange"
            else:
                color = "red"
            return format_html('<span style="color: {};">{}</span>', color, f'{score:.1f}%')
        return "Non corrigé"

    @admin.display(description='Réponses correctes', ordering='correct_answer_count')
    def correct_answers_display(self, obj):
        if obj.is_corrected:
            correct = getattr(obj, 'correct_answer_count', obj.answers.filter(is_correct=True).count())
            total = getattr(obj, 'answer_count', obj.answers.count())
            return f"{correct}/{total}"
        return "-"

    @admin.display(description='Nombre de réponses correctes')
    def correct_answers_count(self, obj):
        return getattr(obj, 'correct_answer_count', obj.answers.filter(is_correct=True).count())

    @admin.display(description='Nombre total de réponses')
    def answers_count(self, obj):
        return getattr(obj, 'answer_count', obj.answers.count())

    @admin.display(description='Durée de la tentative')
    def attempt_duration(self, obj):
        if obj.attempt and obj.attempt.ended_at:
            duration = obj.attempt.ended_at - obj.attempt.started_at
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "Tentative non terminée"


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['submission_candidate', 'question_display', 'response_display', 'is_correct_display',
                    'score_display', 'answered_at']
    list_filter = ['is_correct', 'question__question_type', 'answered_at', 'submission__challenge']
    search_fields = ['submission__candidate__email', 'question__title', 'text', 'selected_choices__text']
    autocomplete_fields = ['submission', 'question']
    readonly_fields = ['answered_at', 'score_display']
    filter_horizontal = ['selected_choices']

    fieldsets = (('Réponse', {'fields': ('submission', 'question', 'text', 'selected_choices', 'is_correct')}),
                 ('Détails', {'fields': ('score_display', 'answered_at'), 'classes': ('collapse',), }),)

    @admin.display(description='Candidat', ordering='submission__candidate__email')
    def submission_candidate(self, obj):
        if not obj.submission or not obj.submission.candidate:
            return "-"
        return obj.submission.candidate.email

    @admin.display(description='Question', ordering='question__title')
    def question_display(self, obj):
        if not obj.question:
            return "-"
        return format_html('{} <span style="color: gray;">({})</span>', obj.question.title,
            obj.question.get_question_type_display())

    @admin.display(description='Réponse')
    def response_display(self, obj):
        if obj.question.is_open_answer:
            return obj.text or "-"

        choices = obj.selected_choices.all()
        if not choices:
            return "-"

        return ", ".join([choice.text for choice in choices])

    @admin.display(description='Correcte', ordering='is_correct', boolean=True)
    def is_correct_display(self, obj):
        return obj.is_correct

    @admin.display(description='Score (%)')
    def score_display(self, obj):
        if obj.is_correct is not None:
            score = obj.average_score * 100
            if score >= 80:
                color = "green"
            elif score >= 50:
                color = "orange"
            else:
                color = "red"
            return format_html('<span style="color: {};">{}</span>', color, f'{score:.1f}%')
        return "-"


@admin.register(APIUsage)
class APIUsageAdmin(admin.ModelAdmin):
    list_display = ['date', 'count_display', 'limit_status']
    search_fields = ['date']
    list_filter = ['date']
    ordering = ['-date']
    readonly_fields = ['usage_chart']

    fieldsets = (('Utilisation', {'fields': ('date', 'count', 'usage_chart')}),)

    @admin.display(description='Nombre de requêtes', ordering='count')
    def count_display(self, obj):
        return f"{obj.count:,}".replace(",", " ")

    @admin.display(description='Statut de limite', ordering='count')
    def limit_status(self, obj):
        percentage = (obj.count / 1500) * 100
        if percentage >= 100:
            color = 'red'
            status = 'Limite atteinte'
        elif percentage >= 75:
            color = 'orange'
            status = 'Proche de la limite'
        else:
            color = 'green'
            status = 'OK'

        return format_html('<span style="color: {};">{} ({})</span>', color, status, f'{percentage:.1f}%')

    @admin.display(description='Graphique d\'utilisation')
    def usage_chart(self, obj):
        percentage = min(100, (obj.count / 1500) * 100)
        color = 'red' if percentage >= 100 else 'orange' if percentage >= 75 else 'green'

        return format_html('<div style="width:100%; background-color:#f0f0f0; height:20px; border-radius:5px;">'
                           '<div style="width:{}%; background-color:{}; height:20px; border-radius:5px;"></div>'
                           '</div>'
                           '<div style="margin-top:5px;">{} sur 1500 requêtes ({})</div>', percentage, color,
            obj.count, f'{percentage:.1f}%')


class PersonalityAnswerInline(admin.TabularInline):
    model = PersonalityAnswer
    extra = 0
    readonly_fields = ['question', 'text', 'selected_choices_display', 'answered_at']
    can_delete = False
    fields = ['question', 'text', 'selected_choices_display', 'answered_at']

    def selected_choices_display(self, obj):
        choices = obj.selected_choices.all()
        if not choices:
            return obj.text or "-"
        return ", ".join([choice.text for choice in choices])

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PersonalityChallenge)
class PersonalityChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'candidate_display', 'questions_count', 'answers_count', 'is_passed', 'corrected']
    search_fields = ['title', 'description', 'candidate__first_name', 'candidate__last_name', 'candidate__email']
    list_filter = ['is_passed', 'corrected']
    readonly_fields = ['slug', 'questions_count', 'answers_count', 'completion_rate']
    inlines = [PersonalityAnswerInline]
    autocomplete_fields = ['candidate', 'questions']
    filter_horizontal = ['questions']

    fieldsets = (('Informations de base', {'fields': ('title', 'description', 'candidate')}),
                 ('Questions', {'fields': ('questions',), }), ('Statut', {'fields': ('is_passed', 'corrected')}),
                 ('Analyse de personnalité', {'fields': ('personality_detail',), 'classes': ('collapse',)}),
                 ('Statistiques',
                  {'fields': ('questions_count', 'answers_count', 'completion_rate'), 'classes': ('collapse',)}),
                 ('Extras', {'fields': ('slug',), 'classes': ('collapse',)}),)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('candidate').prefetch_related('questions',
                                                                                          'answers').annotate(
            answer_count=Count('answers', distinct=True), question_count=Count('questions', distinct=True))

    @admin.display(description='Candidat', ordering='candidate__email')
    def candidate_display(self, obj):
        if not obj.candidate:
            return "-"
        return format_html('{} ({})', obj.candidate.email, obj.candidate.get_full_name() or 'Sans nom')

    @admin.display(description='Nombre de questions', ordering='question_count')
    def questions_count(self, obj):
        return getattr(obj, 'question_count', obj.questions.count())

    @admin.display(description='Nombre de réponses', ordering='answer_count')
    def answers_count(self, obj):
        return getattr(obj, 'answer_count', obj.answers.count())

    @admin.display(description='Taux de complétion (%)')
    def completion_rate(self, obj):
        questions_count = getattr(obj, 'question_count', obj.questions.count())
        answers_count = getattr(obj, 'answer_count', obj.answers.count())

        if questions_count > 0:
            rate = (answers_count / questions_count) * 100
            if rate >= 80:
                color = "green"
            elif rate >= 50:
                color = "orange"
            else:
                color = "red"
            return format_html('<span style="color: {};">{}%</span>', color, f'{rate:.1f}%')
        return "Pas de questions"


@admin.register(PersonalityAnswer)
class PersonalityAnswerAdmin(admin.ModelAdmin):
    list_display = ['submission_title', 'candidate_display', 'question_display', 'response_display', 'answered_at']
    list_filter = ['answered_at', 'submission', 'question__question_type']
    search_fields = ['submission__title', 'submission__candidate__email', 'question__title', 'text',
                     'selected_choices__text']
    autocomplete_fields = ['submission', 'question']
    readonly_fields = ['answered_at']
    filter_horizontal = ['selected_choices']

    fieldsets = (('Réponse', {'fields': ('submission', 'question', 'text', 'selected_choices')}),
                 ('Métadonnées', {'fields': ('answered_at',), 'classes': ('collapse',)}),)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('submission', 'submission__candidate', 'question')

    @admin.display(description='Challenge', ordering='submission__title')
    def submission_title(self, obj):
        if not obj.submission:
            return "-"
        return obj.submission.title

    @admin.display(description='Candidat', ordering='submission__candidate__email')
    def candidate_display(self, obj):
        if not obj.submission or not obj.submission.candidate:
            return "-"
        return obj.submission.candidate.email

    @admin.display(description='Question', ordering='question__title')
    def question_display(self, obj):
        if not obj.question:
            return "-"
        return format_html('{} <span style="color: gray;">({})</span>', obj.question.title,
            obj.question.get_question_type_display())

    @admin.display(description='Réponse')
    def response_display(self, obj):
        if obj.question.is_open_answer:
            return obj.text or "-"

        choices = obj.selected_choices.all()
        if not choices:
            return "-"

        return ", ".join([choice.text for choice in choices])
