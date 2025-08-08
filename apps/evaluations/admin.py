from django.contrib import admin
from django.db.models import Avg, Count, Max, Min
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.evaluations.models import Evaluation, Submission, SubmissionAttempt, Answer, Competition, EvaluationType


class CompetitionInline(admin.StackedInline):
    model = Competition
    extra = 0
    fields = ['started_at', 'ended_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return obj and obj.evaluation_type == EvaluationType.COMPETITION


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ['question', 'is_correct', 'status', 'score', 'delta_time', 'answered_at']
    fields = ['question', 'is_correct', 'status', 'score', 'delta_time']
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'technology_display', 'difficulty', 'evaluation_type', 'competition_status',
                    'questions_count', 'attempts_count', 'average_score']
    search_fields = ['title', 'description', 'technology__name']
    list_filter = ['difficulty', 'technology', 'profession', 'evaluation_type']
    readonly_fields = ['created_at', 'updated_at', 'statistics']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CompetitionInline]

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('title', 'slug', 'description', 'image')
        }),
        (_('Classification'), {
            'fields': ('technology', 'profession', 'difficulty', 'evaluation_type')
        }),
        (_('Statistiques'), {
            'fields': ('statistics',)
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_("Technologie"))
    def technology_display(self, obj):
        if obj.technology and obj.technology.image:
            return format_html('<img src="{}" style="height: 20px;"> {}',
                               obj.technology.image.url, obj.technology.name)
        return obj.technology.name if obj.technology else "-"

    @admin.display(description=_("Statut compétition"))
    def competition_status(self, obj):
        if obj.evaluation_type != EvaluationType.COMPETITION:
            return "-"

        try:
            competition = obj.competition
            from django.utils import timezone
            now = timezone.now()

            if competition.started_at and competition.started_at > now:
                return format_html('<span style="color: orange;">🕐 {}</span>', _("Pas encore commencée"))
            elif competition.ended_at and competition.ended_at < now:
                return format_html('<span style="color: red;">🏁 {}</span>', _("Terminée"))
            else:
                return format_html('<span style="color: green;">🟢 {}</span>', _("Active"))
        except Competition.DoesNotExist:
            return format_html('<span style="color: red;">❌ {}</span>', _("Configuration manquante"))

    @admin.display(description=_("Questions"))
    def questions_count(self, obj):
        published = obj.questions.filter(status='published').count()
        total = obj.questions.count()
        return f"{published} / {total}"

    @admin.display(description=_("Tentatives"))
    def attempts_count(self, obj):
        return obj.attempts.count()

    @admin.display(description=_("Score moyen"))
    def average_score(self, obj):
        avg = obj.attempts.filter(submission__isnull=False).aggregate(avg=Avg('submission__score'))['avg']
        if avg is not None:
            return f"{avg:.1f}"
        return "-"

    @admin.display(description=_("Statistiques détaillées"))
    def statistics(self, obj):
        stats = obj.attempts.filter(submission__isnull=False).aggregate(
            count=Count('id'),
            avg=Avg('submission__score'),
            max=Max('submission__score'),
            min=Min('submission__score'),
        )

        if not stats['count']:
            return _("Aucune tentative terminée pour cette évaluation.")

        return format_html("""
            <div style="margin-top: 10px;">
                <p><strong>Nombre de tentatives terminées:</strong> {count}</p>
                <p><strong>Score moyen:</strong> {avg:.2f}</p>
                <p><strong>Score le plus haut:</strong> {max:.2f}</p>
                <p><strong>Score le plus bas:</strong> {min:.2f}</p>
            </div>
        """, **stats)


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ['id', 'evaluation', 'started_at', 'ended_at', 'is_active', 'participants_count']
    search_fields = ['evaluation__title']
    list_filter = ['started_at', 'ended_at']
    readonly_fields = ['created_at', 'is_active', 'participants_count']

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('evaluation',)
        }),
        (_('Période'), {
            'fields': ('started_at', 'ended_at')
        }),
        (_('Statistiques'), {
            'fields': ('is_active', 'participants_count', 'created_at')
        }),
    )

    @admin.display(description=_("Active"), boolean=True)
    def is_active(self, obj):
        from django.utils import timezone
        now = timezone.now()
        return (obj.started_at is None or obj.started_at <= now) and (obj.ended_at is None or obj.ended_at > now)

    @admin.display(description=_("Participants"))
    def participants_count(self, obj):
        return obj.evaluation.attempts.values('candidate').distinct().count()


class IsFinishedFilter(admin.SimpleListFilter):
    title = _('Tentative terminée')
    parameter_name = 'is_finished'

    def lookups(self, request, model_admin):
        return (
            ('true', _('Oui')),
            ('false', _('Non')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'true':
            return queryset.filter(submission__isnull=False, ended_at__isnull=False)
        elif self.value() == 'false':
            return queryset.filter(submission__isnull=True, ended_at__isnull=True)


@admin.register(SubmissionAttempt)
class SubmissionAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'candidate_display', 'evaluation', 'evaluation_type', 'started_at', 'ended_at', 'is_finished',
                    'score']
    search_fields = ['candidate__username', 'candidate__email', 'evaluation__title']
    list_filter = [IsFinishedFilter, 'evaluation__difficulty', 'evaluation__evaluation_type', 'evaluation']
    readonly_fields = ['started_at', 'answers_preview']
    inlines = [AnswerInline]

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('evaluation', 'candidate')
        }),
        (_('Timing'), {
            'fields': ('started_at', 'ended_at')
        }),
        (_('Résultats'), {
            'fields': ('submission', 'answers_preview')
        }),
    )

    @admin.display(description=_("Type"))
    def evaluation_type(self, obj):
        type_icons = {
            EvaluationType.NORMAL: '📝',
            EvaluationType.COMPETITION: '🏆'
        }
        icon = type_icons.get(obj.evaluation.evaluation_type, '❓')
        return format_html('{} {}', icon, obj.evaluation.get_evaluation_type_display())

    @admin.display(description=_("Réponses"))
    def answers_preview(self, obj):
        answers = obj.answers.all()
        if not answers:
            return _("Aucune réponse enregistrée")

        html = [f"<div style='margin: 10px 0;'><p>{_('Réponses')}:</p><ul>"]

        for answer in answers[:5]:  # Limiter à 5 réponses pour l'aperçu
            status_icons = {
                'correct': '✅',
                'partial': '🟡',
                'incorrect': '❌',
                'timeout': '⏱️',
                'discarded': '🗑️',
                'pending': '⏳'
            }
            icon = status_icons.get(answer.status, '❓')
            html.append(f"<li>{icon} {answer.question} - {answer.score} points</li>")

        if len(answers) > 5:
            html.append(f"<li>... {len(answers) - 5} autres réponses</li>")

        html.append("</ul></div>")
        return format_html("".join(html))

    @admin.display(description=_("Candidat"))
    def candidate_display(self, obj):
        return f"{obj.candidate.get_full_name()} ({obj.candidate.email})"

    @admin.display(description=_("Score"))
    def score(self, obj):
        if obj.submission and obj.submission.score is not None:
            return f"{obj.submission.score:.1f}"
        return "-"

    @admin.display(description=_("Finie"), boolean=True)
    def is_finished(self, obj):
        return obj.is_finished


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'candidate', 'evaluation', 'score', 'submitted_at']
    search_fields = ['attempt__candidate__full_name', 'attempt__candidate__email', 'attempt__evaluation__title']
    readonly_fields = ['submitted_at', 'candidate', 'evaluation']

    @admin.display(description=_("Candidat"))
    def candidate(self, obj):
        return obj.attempt.candidate if hasattr(obj, 'attempt') else "-"

    @admin.display(description=_("Évaluation"))
    def evaluation(self, obj):
        return obj.attempt.evaluation if hasattr(obj, 'attempt') else "-"
