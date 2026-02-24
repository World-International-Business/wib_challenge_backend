from django.contrib import admin
from django.db.models import Avg, Count, Max, Min, Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.evaluations.models import (
    Evaluation, Submission, SubmissionAttempt, Answer, Competition,
    EvaluationType, Candidate, Participant, EvaluationInvitation
)


class DifficultyFilter(admin.SimpleListFilter):
    title = _('Niveau de difficulté')
    parameter_name = 'difficulty'

    def lookups(self, request, model_admin):
        return Evaluation.Difficulty.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(difficulty=self.value())
        return queryset


class EvaluationTypeFilter(admin.SimpleListFilter):
    title = _('Type d\'évaluation')
    parameter_name = 'evaluation_type'

    def lookups(self, request, model_admin):
        return EvaluationType.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(evaluation_type=self.value())
        return queryset


class CompletionStatusFilter(admin.SimpleListFilter):
    title = _('Statut de complétion')
    parameter_name = 'completion_status'

    def lookups(self, request, model_admin):
        return (
            ('completed', _('Terminées')),
            ('in_progress', _('En cours')),
            ('not_started', _('Non commencées')),
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        # Les superusers voient tout. Les utilisateurs liés à une organisation
        # voient uniquement les évaluations publiées par leur organisation.
        org = getattr(user, 'organization', None)
        if not user.is_superuser and org is not None:
            return qs.filter(publisher__organization=org)
        return qs

    def queryset(self, request, queryset):
        if self.value() == 'completed':
            return queryset.filter(submission__isnull=False, ended_at__isnull=False)
        elif self.value() == 'in_progress':
            return queryset.filter(submission__isnull=True, ended_at__isnull=True)
        else:
            return queryset.filter(started_at__isnull=True)


class ScoreRangeFilter(admin.SimpleListFilter):
    title = _('Plage de scores')
    parameter_name = 'score_range'

    def lookups(self, request, model_admin):
        return (
            ('excellent', _('Excellent (90-100%)')),
            ('good', _('Bon (70-89%)')),
            ('average', _('Moyen (50-69%)')),
            ('poor', _('Faible (0-49%)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'excellent':
            return queryset.filter(submission__score__gte=90)
        elif self.value() == 'good':
            return queryset.filter(submission__score__gte=70, submission__score__lt=90)
        elif self.value() == 'average':
            return queryset.filter(submission__score__gte=50, submission__score__lt=70)
        else:
            return queryset.filter(submission__score__lt=50)


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
    readonly_fields = ['question', 'is_correct', 'status', 'score', 'delta_time', 'answered_at', 'status_icon']
    fields = ['question', 'status_icon', 'is_correct', 'score', 'delta_time']
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Statut"))
    def status_icon(self, obj):
        status_icons = {
            'correct': '✅',
            'partial': '🟡',
            'incorrect': '❌',
            'timeout': '⏱️',
            'discarded': '🗑️',
            'pending': '⏳'
        }
        icon = status_icons.get(obj.status, '❓')
        return format_html('{} {}', icon, obj.get_status_display())


class EvaluationInvitationInline(admin.TabularInline):
    model = EvaluationInvitation
    extra = 0
    readonly_fields = ['candidate', 'token', 'invited_at', 'expires_at', 'status_display']
    fields = ['candidate', 'status_display', 'invited_at', 'expires_at']
    can_delete = False

    @admin.display(description=_("Statut"))
    def status_display(self, obj):
        status_colors = {
            'pending': 'orange',
            'accepted': 'green',
            'declined': 'red',
            'expired': 'gray'
        }
        color = status_colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'email', 'owner', 'evaluations_count', 'avg_score', 'created_at']
    search_fields = ['full_name', 'email', 'owner__username']
    list_filter = ['created_at', 'owner']
    readonly_fields = ['created_at', 'updated_at', 'evaluations_summary']

    fieldsets = (
        (_('Informations personnelles'), {
            'fields': ('full_name', 'email')
        }),
        (_('Gestion'), {
            'fields': ('owner',)
        }),
        (_('Statistiques'), {
            'fields': ('evaluations_summary',),
            'classes': ('collapse',)
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_("Évaluations"))
    def evaluations_count(self, obj):
        try:
            participant = obj.participant
            return participant.attempts.count()
        except:
            return 0

    @admin.display(description=_("Score moyen"))
    def avg_score(self, obj):
        try:
            participant = obj.participant
            avg = participant.attempts.filter(submission__isnull=False).aggregate(
                avg=Avg('submission__score'))['avg']
            return f"{avg:.1f}" if avg else "-"
        except:
            return "-"

    @admin.display(description=_("Résumé des évaluations"))
    def evaluations_summary(self, obj):
        try:
            participant = obj.participant
            attempts = participant.attempts.all()
            completed = attempts.filter(submission__isnull=False).count()
            total = attempts.count()

            if not total:
                return _("Aucune évaluation")

            return format_html("""
                <div style="margin-top: 10px;">
                    <p><strong>Total:</strong> {total}</p>
                    <p><strong>Terminées:</strong> {completed}</p>
                    <p><strong>En cours:</strong> {in_progress}</p>
                </div>
            """, total=total, completed=completed, in_progress=total - completed)
        except:
            return _("Aucune donnée")


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['id', 'participant_display', 'type', 'email', 'attempts_count', 'avg_score', 'tests_summary', 'created_at']
    search_fields = ['user__username', 'user__email', 'candidate__full_name', 'candidate__email']
    list_filter = ['type', 'created_at']
    readonly_fields = ['created_at']

    @admin.display(description=_("Participant"))
    def participant_display(self, obj):
        return obj.full_name

    @admin.display(description=_("Email"))
    def email(self, obj):
        return obj.email

    @admin.display(description=_("Tentatives"))
    def attempts_count(self, obj):
        return obj.attempts.count()

    @admin.display(description=_("Score moyen"))
    def avg_score(self, obj):
        avg = obj.attempts.filter(submission__isnull=False).aggregate(avg=Avg('submission__score'))['avg']
        return f"{avg:.1f}" if avg else "-"

    @admin.display(description=_("Tests réussis (tech/log/pers)"))
    def tests_summary(self, obj):
        """Affiche combien de types de tests l'utilisateur a réussis parmi technique/logique/personnalité.

        Un test est considéré comme réussi si au moins une tentative terminée a un score >= 60.
        """
        attempts = obj.attempts.filter(submission__isnull=False)

        required_types = [
            EvaluationType.TECHNICAL,
            EvaluationType.LOGICAL,
            EvaluationType.PERSONALITY,
        ]

        passed_count = 0
        for etype in required_types:
            if attempts.filter(evaluation__evaluation_type=etype, submission__score__gte=60).exists():
                passed_count += 1

        total_required = len(required_types)
        if passed_count == total_required:
            color = 'green'
            icon = '✅'
        elif passed_count > 0:
            color = 'orange'
            icon = '🟡'
        else:
            color = 'red'
            icon = '🔴'

        return format_html('<span style="color: {}">{} {}/{}</span>', color, icon, passed_count, total_required)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'technology_display', 'difficulty_badge', 'evaluation_type_badge',
                    'competition_status', 'questions_count', 'attempts_count', 'average_score', 'is_published']
    search_fields = ['title', 'description', 'technology__name', 'publisher__username']
    list_filter = [DifficultyFilter, EvaluationTypeFilter, 'technology', 'profession', 'archived', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'statistics', 'slug']
    inlines = [CompetitionInline, EvaluationInvitationInline]
    list_per_page = 25

    fieldsets = (
        (_('📋 Informations générales'), {
            'fields': ('title', 'slug', 'description', 'image')
        }),
        (_('🏷️ Classification'), {
            'fields': ('technology', 'profession', 'difficulty', 'evaluation_type', 'questions_order')
        }),
        (_('👤 Gestion'), {
            'fields': ('publisher', 'archived')
        }),
        (_('📊 Statistiques'), {
            'fields': ('statistics',),
            'classes': ('collapse',)
        }),
        (_('⏰ Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_("Technologie"))
    def technology_display(self, obj):
        if obj.technology and obj.technology.image:
            return format_html('<img src="{}" style="height: 20px; margin-right: 5px;"> {}',
                               obj.technology.image.url, obj.technology.name)
        return obj.technology.name if obj.technology else "-"

    @admin.display(description=_("Difficulté"))
    def difficulty_badge(self, obj):
        colors = {
            'beginner': '#28a745',
            'intermediate': '#ffc107',
            'expert': '#dc3545'
        }
        color = colors.get(obj.difficulty, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color, obj.get_difficulty_display()
        )

    @admin.display(description=_("Type"))
    def evaluation_type_badge(self, obj):
        icons = {
            'competition': '🏆',
            'technical': '💻',
            'logical': '🧠',
            'personality': '👤'
        }
        icon = icons.get(obj.evaluation_type, '📝')
        return format_html('{} {}', icon, obj.get_evaluation_type_display())

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

    @admin.display(description=_("Questions"), ordering='questions__count')
    def questions_count(self, obj):
        published = obj.questions.filter(status='published').count()
        total = obj.questions.count()
        color = 'green' if published >= 5 else 'red'
        return format_html('<span style="color: {};">{} / {}</span>', color, published, total)

    @admin.display(description=_("Tentatives"), ordering='attempts__count')
    def attempts_count(self, obj):
        count = obj.attempts.count()
        url = reverse('admin:evaluations_submissionattempt_changelist') + f'?evaluation__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description=_("Score moyen"))
    def average_score(self, obj):
        avg = obj.attempts.filter(submission__isnull=False).aggregate(avg=Avg('submission__score'))['avg']
        if avg is not None:
            color = 'green' if avg >= 70 else 'orange' if avg >= 50 else 'red'
            return format_html('<span style="color: {};">{}</span>', color, avg)
        return "-"

    @admin.display(description=_("Publié"), boolean=True)
    def is_published(self, obj):
        return obj.is_constructed

    @admin.display(description=_("Statistiques détaillées"))
    def statistics(self, obj):
        stats = obj.attempts.filter(submission__isnull=False).aggregate(
            count=Count('id'),
            avg=Avg('submission__score'),
            max=Max('submission__score'),
            min=Min('submission__score'),
        )

        questions_stats = obj.questions.aggregate(
            total=Count('id'),
            published=Count('id', filter=Q(status='published'))
        )

        if not stats['count']:
            return format_html("""
                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                    <h4>📊 Statistiques</h4>
                    <p><strong>Questions:</strong> {published}/{total}</p>
                    <p><em>Aucune tentative terminée pour cette évaluation.</em></p>
                </div>
            """, **questions_stats)

        return format_html("""
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                <h4>📊 Statistiques détaillées</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div>
                        <p><strong>📝 Questions:</strong> {published}/{total}</p>
                        <p><strong>🎯 Tentatives terminées:</strong> {count}</p>
                    </div>
                    <div>
                        <p><strong>📈 Score moyen:</strong> {avg:.2f}</p>
                        <p><strong>🏆 Meilleur score:</strong> {max:.2f}</p>
                        <p><strong>📉 Score le plus bas:</strong> {min:.2f}</p>
                    </div>
                </div>
            </div>
        """, **{**stats, **questions_stats})


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ['id', 'evaluation_link', 'period_display', 'is_active', 'participants_count', 'avg_score']
    search_fields = ['evaluation__title']
    list_filter = ['started_at', 'ended_at', 'evaluation__difficulty']
    readonly_fields = ['created_at', 'is_active', 'participants_count', 'competition_stats']

    fieldsets = (
        (_('🏆 Informations générales'), {
            'fields': ('evaluation',)
        }),
        (_('⏰ Période'), {
            'fields': ('started_at', 'ended_at')
        }),
        (_('📊 Statistiques'), {
            'fields': ('is_active', 'participants_count', 'competition_stats', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_("Évaluation"))
    def evaluation_link(self, obj):
        url = reverse('admin:evaluations_evaluation_change', args=[obj.evaluation.id])
        return format_html('<a href="{}">{}</a>', url, obj.evaluation.title)

    @admin.display(description=_("Période"))
    def period_display(self, obj):
        if obj.started_at and obj.ended_at:
            return format_html('Du {} au {}',
                               obj.started_at.strftime('%d/%m/%Y'),
                               obj.ended_at.strftime('%d/%m/%Y'))
        return "Non définie"

    @admin.display(description=_("Active"), boolean=True)
    def is_active(self, obj):
        from django.utils import timezone
        now = timezone.now()
        return (obj.started_at is None or obj.started_at <= now) and (obj.ended_at is None or obj.ended_at > now)

    @admin.display(description=_("Participants"))
    def participants_count(self, obj):
        return obj.evaluation.attempts.values('participant').distinct().count()

    @admin.display(description=_("Score moyen"))
    def avg_score(self, obj):
        avg = obj.evaluation.attempts.filter(submission__isnull=False).aggregate(avg=Avg('submission__score'))['avg']
        return f"{avg:.1f}" if avg else "-"

    @admin.display(description=_("Statistiques de la compétition"))
    def competition_stats(self, obj):
        stats = obj.evaluation.attempts.filter(submission__isnull=False).aggregate(
            total=Count('id'),
            avg=Avg('submission__score'),
            participants=Count('participant', distinct=True)
        )

        return format_html("""
            <div style="background: #e3f2fd; padding: 15px; border-radius: 5px;">
                <h4>🏆 Statistiques de la compétition</h4>
                <p><strong>Participants uniques:</strong> {participants}</p>
                <p><strong>Tentatives terminées:</strong> {total}</p>
                <p><strong>Score moyen:</strong> {avg:.2f}</p>
            </div>
        """, **stats) if stats['total'] else "Aucune donnée disponible"


class IsFinishedFilter(admin.SimpleListFilter):
    title = _('Tentative terminée')
    parameter_name = 'is_finished'

    def lookups(self, request, model_admin):
        return (
            ('true', _('✅ Terminées')),
            ('false', _('⏳ En cours')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'true':
            return queryset.filter(submission__isnull=False, ended_at__isnull=False)
        elif self.value() == 'false':
            return queryset.filter(submission__isnull=True, ended_at__isnull=True)
        else:
            return queryset


@admin.register(SubmissionAttempt)
class SubmissionAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'participant_display', 'evaluation_link', 'evaluation_type', 'started_at',
                    'duration', 'is_finished', 'score_display', 'answers_count']
    search_fields = ['participant__user__username', 'participant__user__email',
                     'participant__candidate__full_name', 'participant__candidate__email', 'evaluation__title']
    list_filter = [
        IsFinishedFilter,
        ScoreRangeFilter,
        'evaluation__difficulty',
        'evaluation__evaluation_type',
        'evaluation__publisher__organization',  # filtrer par organisation de l'évaluation
        'evaluation',
        'started_at',
    ]
    readonly_fields = ['started_at', 'answers_preview', 'attempt_summary']
    inlines = [AnswerInline]
    list_per_page = 25

    fieldsets = (
        (_('👤 Informations générales'), {
            'fields': ('evaluation', 'participant')
        }),
        (_('⏱️ Timing'), {
            'fields': ('started_at', 'ended_at')
        }),
        (_('📋 Résultats'), {
            'fields': ('submission', 'attempt_summary', 'answers_preview')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        org = getattr(user, 'organization', None)
        if not user.is_superuser and org is not None:
            return qs.filter(evaluation__publisher__organization=org)
        return qs

    @admin.display(description=_("Participant"))
    def participant_display(self, obj):
        name = obj.participant.full_name
        email = obj.participant.email
        return format_html('{}<br><small style="color: #666;">{}</small>', name, email)

    @admin.display(description=_("Évaluation"))
    def evaluation_link(self, obj):
        url = reverse('admin:evaluations_evaluation_change', args=[obj.evaluation.id])
        return format_html('<a href="{}">{}</a>', url, obj.evaluation.title)

    @admin.display(description=_("Type"))
    def evaluation_type(self, obj):
        type_icons = {
            EvaluationType.TECHNICAL: '💻',
            EvaluationType.COMPETITION: '🏆',
            EvaluationType.LOGICAL: '🧠',
            EvaluationType.PERSONALITY: '👤'
        }
        icon = type_icons.get(obj.evaluation.evaluation_type, '❓')
        return format_html('{} {}', icon, obj.evaluation.get_evaluation_type_display())

    @admin.display(description=_("Durée"))
    def duration(self, obj):
        if obj.started_at and obj.ended_at:
            delta = obj.ended_at - obj.started_at
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} min"
        elif obj.started_at:
            from django.utils import timezone
            delta = timezone.now() - obj.started_at
            minutes = int(delta.total_seconds() / 60)
            return format_html('<span style="color: orange;">{} min (en cours)</span>', minutes)
        return "-"

    @admin.display(description=_("Score"))
    def score_display(self, obj):
        if obj.submission and obj.submission.score is not None:
            score = obj.submission.score
            if score >= 80:
                color = 'green'
                icon = '🟢'
            elif score >= 60:
                color = 'orange'
                icon = '🟡'
            else:
                color = 'red'
                icon = '🔴'
            try:
                score_value = float(score)
                score_str = f"{score_value:.1f}"
            except (TypeError, ValueError):
                # Si le score ne peut pas être converti proprement en float, on l'affiche tel quel sans formatage décimal
                score_str = str(score)

            return format_html('<span style="color: {};">{} {}</span>', color, icon, score_str)
        return "-"

    @admin.display(description=_("Réponses"))
    def answers_count(self, obj):
        total = obj.answers.count()
        correct = obj.answers.filter(is_correct=True).count()
        url = reverse('admin:evaluations_answer_changelist') + f'?attempt__id__exact={obj.id}'
        return format_html('<a href="{}">{}/{}</a>', url, correct, total)

    @admin.display(description=_("Finie"), boolean=True)
    def is_finished(self, obj):
        return obj.is_finished

    @admin.display(description=_("Résumé de la tentative"))
    def attempt_summary(self, obj):
        answers = obj.answers.all()
        if not answers:
            return _("Aucune réponse enregistrée")

        stats = answers.aggregate(
            total=Count('id'),
            correct=Count('id', filter=Q(is_correct=True)),
            incorrect=Count('id', filter=Q(is_correct=False)),
            pending=Count('id', filter=Q(is_correct__isnull=True))
        )

        return format_html("""
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                <h4>📊 Résumé des réponses</h4>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div><strong>✅ Correctes:</strong> {correct}</div>
                    <div><strong>❌ Incorrectes:</strong> {incorrect}</div>
                    <div><strong>⏳ En attente:</strong> {pending}</div>
                </div>
                <p style="margin-top: 10px;"><strong>Total:</strong> {total} réponses</p>
            </div>
        """, **stats)

    @admin.display(description=_("Aperçu des réponses"))
    def answers_preview(self, obj):
        answers = obj.answers.all()[:5]
        if not answers:
            return _("Aucune réponse enregistrée")

        html = ['<div style="margin: 10px 0;"><h4>📝 Dernières réponses:</h4><ul>']

        for answer in answers:
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

        if obj.answers.count() > 5:
            html.append(f"<li>... {obj.answers.count() - 5} autres réponses</li>")

        html.append("</ul></div>")
        return format_html("".join(html))


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'participant_name', 'question_title', 'status_display', 'is_correct',
                    'score', 'delta_time', 'answered_at']
    search_fields = ['attempt__participant__user__username', 'attempt__participant__candidate__full_name',
                     'question__title']
    list_filter = ['status', 'is_correct', 'answered_at', 'question__difficulty']
    readonly_fields = ['answered_at', 'attempt', 'question']

    @admin.display(description=_("Participant"))
    def participant_name(self, obj):
        return obj.attempt.participant.full_name

    @admin.display(description=_("Question"))
    def question_title(self, obj):
        return obj.question.title

    @admin.display(description=_("Statut"))
    def status_display(self, obj):
        status_icons = {
            'correct': '✅',
            'partial': '🟡',
            'incorrect': '❌',
            'timeout': '⏱️',
            'discarded': '🗑️',
            'pending': '⏳'
        }
        icon = status_icons.get(obj.status, '❓')
        return format_html('{} {}', icon, obj.get_status_display())


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'participant_name', 'evaluation_name', 'score_badge', 'submitted_at']
    search_fields = ['attempt__participant__user__username', 'attempt__participant__candidate__full_name',
                     'attempt__evaluation__title']
    list_filter = [
        'attempt__evaluation__publisher__organization',  # filtrer les soumissions par organisation
        'submitted_at',
    ]
    readonly_fields = ['submitted_at', 'participant_name', 'evaluation_name', 'attempt_link']

    fieldsets = (
        (_('📋 Informations générales'), {
            'fields': ('attempt_link', 'participant_name', 'evaluation_name')
        }),
        (_('📊 Résultats'), {
            'fields': ('score', 'personality_detail')
        }),
        (_('⏰ Métadonnées'), {
            'fields': ('submitted_at',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        org = getattr(user, 'organization', None)
        if not user.is_superuser and org is not None:
            return qs.filter(attempt__evaluation__publisher__organization=org)
        return qs

    @admin.display(description=_("Participant"))
    def participant_name(self, obj):
        return obj.attempt.participant.full_name if hasattr(obj, 'attempt') else "-"

    @admin.display(description=_("Évaluation"))
    def evaluation_name(self, obj):
        return obj.attempt.evaluation.title if hasattr(obj, 'attempt') else "-"

    @admin.display(description=_("Score"))
    def score_badge(self, obj):
        if obj.score is not None:
            if obj.score_percent >= 80:
                color = '#28a745'
                icon = '🏆'
            elif obj.score_percent >= 60:
                color = '#ffc107'
                icon = '🥈'
            else:
                color = '#dc3545'
                icon = '📉'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 15px;">{} {}</span>',
                color, icon, obj.score_percent
            )
        return "-"

    @admin.display(description=_("Tentative"))
    def attempt_link(self, obj):
        if hasattr(obj, 'attempt'):
            url = reverse('admin:evaluations_submissionattempt_change', args=[obj.attempt.id])
            return format_html('<a href="{}">Voir la tentative #{}</a>', url, obj.attempt.id)
        return "-"


@admin.register(EvaluationInvitation)
class EvaluationInvitationAdmin(admin.ModelAdmin):
    list_display = ['id', 'candidate_name', 'evaluation_title', 'status_badge', 'invited_at',
                    'expires_at', 'is_valid_status']
    search_fields = ['candidate__full_name', 'candidate__email', 'evaluation__title']
    list_filter = ['status', 'invited_at', 'expires_at']
    readonly_fields = ['token', 'invited_at', 'is_valid_status']

    fieldsets = (
        (_('📧 Invitation'), {
            'fields': ('evaluation', 'candidate', 'token')
        }),
        (_('⏰ Timing'), {
            'fields': ('invited_at', 'expires_at', 'is_valid_status')
        }),
        (_('📊 Statut'), {
            'fields': ('status',)
        }),
    )

    @admin.display(description=_("Candidat"))
    def candidate_name(self, obj):
        return f"{obj.candidate.full_name} ({obj.candidate.email})"

    @admin.display(description=_("Évaluation"))
    def evaluation_title(self, obj):
        url = reverse('admin:evaluations_evaluation_change', args=[obj.evaluation.id])
        return format_html('<a href="{}">{}</a>', url, obj.evaluation.title)

    @admin.display(description=_("Statut"))
    def status_badge(self, obj):
        status_colors = {
            'pending': '#ffc107',
            'accepted': '#28a745',
            'declined': '#dc3545',
            'expired': '#6c757d'
        }
        status_icons = {
            'pending': '⏳',
            'accepted': '✅',
            'declined': '❌',
            'expired': '⏰'
        }
        color = status_colors.get(obj.status, '#6c757d')
        icon = status_icons.get(obj.status, '❓')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{} {}</span>',
            color, icon, obj.get_status_display()
        )

    @admin.display(description=_("Valide"), boolean=True)
    def is_valid_status(self, obj):
        return obj.is_valid
