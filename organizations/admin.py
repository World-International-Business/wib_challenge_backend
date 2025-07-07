from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count
from decouple import config

from .models import (
    Organization, Candidate, OrgEvaluation, OrgQuestion,
    OrgChoice, OrgSubmissionAttempt, OrgSubmission,
    OrgAnswer, EvaluationInvitation
)


class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 0
    fields = ('full_name', 'email', 'created_at')
    readonly_fields = ('created_at',)


class EvaluationInline(admin.TabularInline):
    model = OrgEvaluation
    extra = 0
    fields = ('title', 'questions_count', 'archived', 'created_at', 'type')
    readonly_fields = ('questions_count', 'created_at', 'type')

    @admin.display(description=_('Nombre de questions'))
    def questions_count(self, obj):
        return obj.questions.count()


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'website', 'city', 'country', 'candidates_count', 'evaluations_count',
                    'created_at')
    list_filter = ('country', 'city', 'created_at')
    search_fields = ('name', 'account__email', 'city', 'country')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CandidateInline, EvaluationInline]
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('name', 'description', 'account')
        }),
        (_('Localisation'), {
            'fields': ('address', 'city', 'country')
        }),
        (_('Médias'), {
            'fields': ('logo', 'website')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            candidates_count=Count('candidates', distinct=True),
            evaluations_count=Count('evaluations', distinct=True)
        )

    @admin.display(description=_('Nombre de candidats'), ordering='candidates_count')
    def candidates_count(self, obj):
        return obj.candidates_count

    @admin.display(description=_('Nombre d\'évaluations'), ordering='evaluations_count')
    def evaluations_count(self, obj):
        return obj.evaluations_count


class InvitationInline(admin.TabularInline):
    model = EvaluationInvitation
    extra = 0
    fields = ('candidate', 'status', 'invited_at', 'expires_at')
    readonly_fields = ('invited_at',)


class AttemptsInline(admin.TabularInline):
    model = OrgSubmissionAttempt
    extra = 0
    fields = ('candidate', 'started_at', 'ended_at',
              'is_completed', 'corrected', 'submission_link')
    readonly_fields = ('started_at', 'ended_at', 'submission_link')

    @admin.display(description=_('Soumission'))
    def submission_link(self, obj):
        if obj.submission:
            url = reverse('admin:organizations_orgsubmission_change', args=[
                obj.submission.id])
            return format_html('<a href="{}">{}</a>', url, _('Voir la soumission'))
        return _('Pas de soumission')


class OrgChoiceInline(admin.TabularInline):
    model = OrgChoice
    extra = 1
    fields = ('text', 'is_correct')


class OrgQuestionsInline(admin.TabularInline):
    model = OrgQuestion
    extra = 0
    fields = ('text', 'technology', 'difficulty', 'duration')
    show_change_link = True


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'organization',
                    'created_at', 'attempts_count')
    list_filter = ('organization', 'created_at')
    search_fields = ('full_name', 'email')
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            attempts_count=Count('attempts', distinct=True)
        )

    @admin.display(description=_('Tentatives'), ordering='attempts_count')
    def attempts_count(self, obj):
        return obj.attempts_count


@admin.register(OrgEvaluation)
class OrgEvaluationAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'type', 'profession', 'questions_count',
                    'attempts_count', 'is_ready', 'archived', 'created_at')
    list_filter = ('organization', 'archived', 'created_at', 'type', 'profession')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'slug', 'is_ready', 'max_score')
    inlines = [OrgQuestionsInline, InvitationInline, AttemptsInline]
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('title', 'description', 'type', 'organization', 'profession', 'slug')
        }),
        (_('Configuration'), {
            'fields': ('questions_order', 'archived')
        }),
        (_('Statistiques'), {
            'fields': ('is_ready', 'max_score'),
            'classes': ('collapse',),
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            questions_count=Count('questions', distinct=True),
            attempts_count=Count('attempts', distinct=True)
        )

    @admin.display(description=_('Nombre de questions'), ordering='questions_count')
    def questions_count(self, obj):
        return obj.questions_count

    @admin.display(description=_('Nombre de tentatives'), ordering='attempts_count')
    def attempts_count(self, obj):
        return obj.attempts_count


@admin.register(OrgQuestion)
class OrgQuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text_preview', 'evaluation',
                    'technology', 'difficulty', 'duration', 'weight', 'created_at')
    list_filter = ('evaluation', 'technology', 'difficulty', 'created_at')
    search_fields = ('text', 'explanation')
    inlines = [OrgChoiceInline]
    readonly_fields = ('created_at', 'updated_at', 'weight')
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('evaluation', 'technology', 'original_question')
        }),
        (_('Contenu'), {
            'fields': ('text', 'explanation', 'difficulty', 'duration', 'weight')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Question'))
    def text_preview(self, obj):
        return obj.text[:50] + ('...' if len(obj.text) > 50 else '')


class OrgAnswerInline(admin.TabularInline):
    model = OrgAnswer
    extra = 0
    fields = ('question', 'is_correct', 'score',
              'delta_time', 'status', 'answered_at')
    readonly_fields = ('question', 'is_correct', 'score',
                       'delta_time', 'status', 'answered_at')
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OrgSubmissionAttempt)
class OrgSubmissionAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'candidate', 'evaluation', 'started_at',
                    'ended_at', 'is_completed', 'corrected', 'submission_link')
    list_filter = ('evaluation', 'is_completed', 'corrected', 'started_at')
    search_fields = ('candidate__full_name',
                     'candidate__email', 'evaluation__title')
    readonly_fields = ('started_at', 'ended_at', 'submission_link', 'created_at', 'updated_at')
    inlines = [OrgAnswerInline]
    filter_horizontal = ('questions',)
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('candidate', 'evaluation', 'is_completed', 'corrected')
        }),
        (_('Questions'), {
            'fields': ('questions',)
        }),
        (_('Progrès'), {
            'fields': ('started_at', 'ended_at', 'submission_link')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Soumission'))
    def submission_link(self, obj):
        if obj.submission:
            url = reverse('admin:organizations_orgsubmission_change', args=[
                obj.submission.id])
            return format_html('<a href="{}">{}</a>', url, str(obj.submission))
        return _('Pas de soumission')


@admin.register(OrgSubmission)
class OrgSubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_candidate', 'get_evaluation',
                    'score', 'submitted_at')
    list_filter = ('attempt__evaluation', 'score', 'submitted_at')
    search_fields = ('attempt__candidate__full_name',
                     'attempt__candidate__email', 'attempt__evaluation__title')
    readonly_fields = ('score', 'submitted_at', 'candidate_detail',
                       'evaluation_detail', 'answers_summary', 'created_at', 'updated_at')
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('candidate_detail', 'evaluation_detail')
        }),
        (_('Résultats'), {
            'fields': ('score', 'personality_detail', 'submitted_at', 'answers_summary')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Candidat'))
    def get_candidate(self, obj):
        if hasattr(obj, 'attempt') and obj.attempt and obj.attempt.candidate:
            return obj.attempt.candidate
        return _('Inconnu')

    @admin.display(description=_('Évaluation'))
    def get_evaluation(self, obj):
        if hasattr(obj, 'attempt') and obj.attempt and obj.attempt.evaluation:
            return obj.attempt.evaluation
        return _('Inconnue')

    @admin.display(description=_('Candidat'))
    def candidate_detail(self, obj):
        if hasattr(obj, 'attempt') and obj.attempt and obj.attempt.candidate:
            return format_html('<strong>{}</strong> ({})',
                               obj.attempt.candidate.full_name,
                               obj.attempt.candidate.email)
        return _('Candidat inconnu')

    @admin.display(description=_('Évaluation'))
    def evaluation_detail(self, obj):
        if hasattr(obj, 'attempt') and obj.attempt and obj.attempt.evaluation:
            return format_html('<a href="{}">{}</a>',
                               reverse('admin:organizations_orgevaluation_change',
                                       args=[obj.attempt.evaluation.id]),
                               obj.attempt.evaluation.title)
        return _('Évaluation inconnue')

    @admin.display(description=_('Résumé des réponses'))
    def answers_summary(self, obj):
        if not hasattr(obj, 'attempt'):
            return _('Aucune tentative associée')

        answers = obj.attempt.answers.all()
        total = answers.count()
        correct = answers.filter(is_correct=True).count()

        if total == 0:
            return _('Aucune réponse')

        percentage = int(correct / total * 100)
        color = '#4caf50' if correct / total >= 0.7 else '#ff9800' if correct / total >= 0.5 else '#f44336'

        return format_html(
            '<div style="margin-bottom: 10px;">'
            '<strong>{}</strong> réponse(s) correcte(s) sur <strong>{}</strong> question(s)'
            '</div>'
            '<div style="width: 100%; background-color: #f0f0f0; height: 20px; border-radius: 5px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 5px;"></div>'
            '</div>',
            correct,
            total,
            percentage,
            color
        )


@admin.register(OrgAnswer)
class OrgAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_candidate', 'get_question',
                    'is_correct', 'score', 'delta_time', 'status', 'answered_at')
    list_filter = ('is_correct', 'status', 'answered_at')
    search_fields = ('attempt__candidate__full_name',
                     'attempt__candidate__email', 'question__text')
    readonly_fields = ('is_correct', 'score', 'delta_time',
                       'status', 'answered_at', 'selected_choices_display', 'created_at', 'updated_at')
    exclude = ('selected_choices',)
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('attempt', 'question')
        }),
        (_('Réponses'), {
            'fields': ('selected_choices_display', 'is_correct')
        }),
        (_('Résultats'), {
            'fields': ('score', 'status', 'delta_time', 'answered_at')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Candidat'))
    def get_candidate(self, obj):
        if hasattr(obj, 'attempt') and obj.attempt and obj.attempt.candidate:
            return obj.attempt.candidate
        return _('Inconnu')

    @admin.display(description=_('Question'))
    def get_question(self, obj):
        return obj.question.text[:50] + ('...' if len(obj.question.text) > 50 else '')

    @admin.display(description=_('Choix sélectionnés'))
    def selected_choices_display(self, obj):
        choices = obj.selected_choices.all()
        if not choices:
            return _('Aucune réponse sélectionnée')

        result = '<ul>'
        for choice in choices:
            style = 'color: green; font-weight: bold;' if choice.is_correct else 'color: red; text-decoration: line-through;'
            result += f'<li style="{style}">{choice.text}</li>'
        result += '</ul>'

        correct_choices = obj.question.choices.filter(is_correct=True)
        if not any(c in choices for c in correct_choices):
            result += '<div style="margin-top: 10px;"><strong>Réponses correctes attendues:</strong></div><ul>'
            for choice in correct_choices:
                result += f'<li style="color: green;">{choice.text}</li>'
            result += '</ul>'

        return format_html(result)


@admin.register(OrgChoice)
class OrgChoiceAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct', 'created_at')
    list_filter = ('is_correct', 'created_at')
    search_fields = ('text', 'question__text')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('question', 'text', 'is_correct')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(EvaluationInvitation)
class EvaluationInvitationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'evaluation', 'status', 'invited_at', 'expires_at', 'is_valid', 'token_link')
    list_filter = ('status', 'invited_at', 'expires_at')
    search_fields = ('candidate__full_name', 'candidate__email', 'evaluation__title')
    readonly_fields = ('invited_at', 'is_valid', 'token_link', 'created_at', 'updated_at', 'token')
    actions = ['send_reminder_email']
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('evaluation', 'candidate', 'status')
        }),
        (_('Invitation'), {
            'fields': ('token', 'token_link')
        }),
        (_('Dates'), {
            'fields': ('invited_at', 'expires_at', 'is_valid')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Lien d\'invitation'))
    def token_link(self, obj):
        if obj.token:
            # Exemple d'URL, à adapter selon votre configuration
            base_url = config('FRONTEND_INVITATION_URL', default='')
            return format_html('<a href="{}{}" target="_blank">{}{}</a>',
                               base_url, obj.token, base_url, obj.token)
        return _('Pas de token généré')

    @admin.action(description=_('Envoyer un email de rappel'))
    def send_reminder_email(self, request, queryset):
        from organizations.utils import send_reminder_email

        sent_count = 0
        for invitation in queryset:
            if invitation.status == EvaluationInvitation.Status.PENDING and invitation.is_valid:
                try:
                    send_reminder_email(request, invitation)
                    sent_count += 1
                except Exception as e:
                    self.message_user(request,
                                      f"Erreur lors de l'envoi du rappel pour {invitation.candidate.email}: {str(e)}",
                                      level='ERROR')

        if sent_count > 0:
            self.message_user(request, f"{sent_count} email(s) de rappel envoyé(s) avec succès.")
        else:
            self.message_user(request,
                              "Aucun email de rappel envoyé. Vérifiez que les invitations sont en attente et valides.",
                              level='WARNING')
