from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.questions.models import Question, Choice


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1
    min_num = 2
    max_num = 6
    fields = ['text', 'is_correct']
    verbose_name = _("Choix de réponse")
    verbose_name_plural = _("Choix de réponses")


class DifficultyFilter(admin.SimpleListFilter):
    title = _('Difficulté')
    parameter_name = 'difficulty'

    def lookups(self, request, model_admin):
        return Question.Difficulty.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(difficulty=self.value())
        return queryset


class StatusFilter(admin.SimpleListFilter):
    title = _('Statut')
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return Question.Status.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title_preview', 'difficulty_badge', 'status_badge', 'publisher_info',
        'technology_name', 'choices_count', 'weight_display', 'duration', 'created_at'
    ]
    list_display_links = ['id', 'title_preview']
    list_filter = [DifficultyFilter, StatusFilter, 'technology', 'publisher', 'created_at']
    search_fields = ['title', 'description', 'explanation', 'publisher__email', 'publisher__first_name',
                     'publisher__last_name', 'technology__name']
    readonly_fields = ['created_at', 'updated_at', 'choices_preview', 'weight_display']
    inlines = [ChoiceInline]
    save_on_top = True
    list_per_page = 25

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('title', 'description', 'explanation'),
            'description': _("Contenu principal de la question")
        }),
        (_('Classification'), {
            'fields': ('difficulty', 'status', 'duration', 'weight_display'),
            'description': _("Paramètres de classification et difficulté")
        }),
        (_('Relations'), {
            'fields': ('publisher', 'technology'),
            'description': _("Relations avec les autres modèles")
        }),
        (_('Choix de réponses'), {
            'fields': ('choices_preview',),
            'description': _("Aperçu des choix de réponses"),
            'classes': ('collapse',)
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['make_published', 'make_rejected', 'make_pending']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('publisher', 'technology').prefetch_related('choices')

    @admin.display(description=_("Titre"), ordering='title')
    def title_preview(self, obj):
        """Affiche une version tronquée du titre de la question"""
        if len(obj.title) > 50:
            return f"{obj.title[:50]}..."
        return obj.title

    @admin.display(description=_("Difficulté"))
    def difficulty_badge(self, obj):
        """Affiche la difficulté avec une couleur"""
        colors = {
            Question.Difficulty.EASY: '#28a745',
            Question.Difficulty.MEDIUM: '#ffc107',
            Question.Difficulty.HARD: '#dc3545'
        }
        color = colors.get(obj.difficulty, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{}</span>',
            color,
            obj.get_difficulty_display()
        )

    @admin.display(description=_("Statut"))
    def status_badge(self, obj):
        """Affiche le statut avec une couleur"""
        colors = {
            Question.Status.PENDING: '#ffc107',
            Question.Status.PUBLISHED: '#28a745',
            Question.Status.REJECTED: '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{}</span>',
            color,
            obj.get_status_display()
        )

    @admin.display(description=_("Éditeur"))
    def publisher_info(self, obj):
        """Affiche des informations sur l'éditeur de la question"""
        if obj.publisher:
            return format_html('<a href="{}">{}</a> ({})',
                               reverse('admin:accounts_user_change', args=[obj.publisher.id]),
                               obj.publisher.full_name or obj.publisher.email,
                               obj.publisher.email)
        return _("Inconnu")

    @admin.display(description=_("Technologie"))
    def technology_name(self, obj):
        """Affiche le nom de la technologie avec son icône si disponible"""
        if not obj.technology:
            return _("Non spécifiée")

        if hasattr(obj.technology, 'image') and obj.technology.image:
            return format_html('<img src="{}" style="max-height: 20px; vertical-align: middle;" /> {}',
                               obj.technology.image.url,
                               obj.technology.name)
        return obj.technology.name

    @admin.display(description=_("Nb. choix"))
    def choices_count(self, obj):
        """Affiche le nombre de choix liés à la question"""
        count = obj.choices.count()
        correct_count = obj.choices.filter(is_correct=True).count()

        if count == 0:
            return format_html('<span style="color: red;">0</span>')
        elif correct_count == 0:
            return format_html('<span style="color: orange;" title="Aucune bonne réponse">{}</span>', count)
        elif correct_count > 1:
            return format_html('<span style="color: blue;" title="Plusieurs bonnes réponses">{}</span>', count)
        return format_html('<span style="color: green;" title="Une bonne réponse">{}</span>', count)

    @admin.display(description=_("Poids"))
    def weight_display(self, obj):
        """Affiche le poids de la question"""
        return f"{obj.weight} pts"

    @admin.display(description=_("Aperçu des choix"))
    def choices_preview(self, obj):
        """Affiche un aperçu des choix disponibles pour la question"""
        choices = obj.choices.all()
        if not choices:
            return format_html('<span style="color: red;">Aucun choix disponible</span>')

        html = ['<ul style="margin: 0; padding-left: 20px;">']
        for choice in choices:
            status = '✅' if choice.is_correct else '❌'
            text_preview = choice.text[:100] + ("..." if len(choice.text) > 100 else "")
            html.append(f'<li>{status} {text_preview}</li>')
        html.append('</ul>')

        return format_html(''.join(html))

    @admin.action(description=_("Marquer comme publiées"))
    def make_published(self, request, queryset):
        """Action pour marquer les questions sélectionnées comme publiées"""
        updated = queryset.update(status=Question.Status.PUBLISHED)
        self.message_user(request, _(f"{updated} question(s) ont été marquées comme publiées."))

    @admin.action(description=_("Marquer comme rejetées"))
    def make_rejected(self, request, queryset):
        """Action pour marquer les questions sélectionnées comme rejetées"""
        updated = queryset.update(status=Question.Status.REJECTED)
        self.message_user(request, _(f"{updated} question(s) ont été marquées comme rejetées."))

    @admin.action(description=_("Marquer comme en attente"))
    def make_pending(self, request, queryset):
        """Action pour marquer les questions sélectionnées comme en attente"""
        updated = queryset.update(status=Question.Status.PENDING)
        self.message_user(request, _(f"{updated} question(s) ont été marquées comme en attente."))

    def changelist_view(self, request, extra_context=None):
        """Ajoute des statistiques à la vue liste"""
        extra_context = extra_context or {}

        # Statistiques globales
        total_questions = Question.objects.count()
        published_questions = Question.objects.filter(status=Question.Status.PUBLISHED).count()
        pending_questions = Question.objects.filter(status=Question.Status.PENDING).count()

        difficulty_stats = Question.objects.values('difficulty').annotate(count=Count('id'))

        extra_context.update({
            'total_questions': total_questions,
            'published_questions': published_questions,
            'pending_questions': pending_questions,
            'difficulty_stats': difficulty_stats,
        })

        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'text_preview', 'is_correct_display', 'question_link', 'created_at']
    list_display_links = ['id', 'text_preview']
    list_filter = ['is_correct', 'question__difficulty', 'question__status', 'question__technology']
    search_fields = ['text', 'question__title', 'question__description']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('question', 'text', 'is_correct')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('question', 'question__technology')

    @admin.display(description=_("Texte"), ordering='text')
    def text_preview(self, obj):
        """Affiche une version tronquée du texte du choix"""
        if len(obj.text) > 80:
            return f"{obj.text[:80]}..."
        return obj.text

    @admin.display(description=_("Correct"), boolean=True)
    def is_correct_display(self, obj):
        """Affiche si le choix est correct"""
        return obj.is_correct

    @admin.display(description=_("Question"))
    def question_link(self, obj):
        """Affiche le lien vers la question associée"""
        if obj.question:
            return format_html('<a href="{}">{}</a>',
                               reverse('admin:questions_question_change', args=[obj.question.id]),
                               obj.question.title[:50] + ('...' if len(obj.question.title) > 50 else ''))
        return _("Inconnue")
