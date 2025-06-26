from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from questions.models import Question, Choice


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1
    min_num = 2
    fields = ['text', 'is_correct']
    verbose_name = _("Choix de réponse")
    verbose_name_plural = _("Choix de réponses")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'text_preview', 'difficulty', 'status', 'publisher_info', 'technology_name', 'choices_count',
                    'created_at']
    list_filter = ['status', 'difficulty', 'technology', 'evaluation']
    search_fields = ['text', 'explanation', 'publisher__email', 'publisher__username', 'technology__name']
    readonly_fields = ['created_at', 'updated_at', 'choices_preview']
    inlines = [ChoiceInline]
    save_on_top = True

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('text', 'explanation'),
            'description': _("Contenu principal de la question")
        }),
        (_('Classification'), {
            'fields': ('difficulty', 'status', 'duration'),
            'description': _("Paramètres de classification et difficulté")
        }),
        (_('Relations'), {
            'fields': ('publisher', 'evaluation', 'technology'),
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

    actions = ['make_published', 'make_rejected']

    @admin.display(description=_("Texte"))
    def text_preview(self, obj):
        """Affiche une version tronquée du texte de la question"""
        if len(obj.text) > 50:
            return f"{obj.text[:50]}..."
        return obj.text

    @admin.display(description=_("Éditeur"))
    def publisher_info(self, obj):
        """Affiche des informations sur l'éditeur de la question"""
        if obj.publisher:
            return format_html('<a href="{}">{}</a> ({})',
                               reverse('admin:accounts_user_change', args=[obj.publisher.id]),
                               obj.publisher.username,
                               obj.publisher.email)
        return _("Inconnu")

    @admin.display(description=_("Technologie"))
    def technology_name(self, obj):
        """Affiche le nom de la technologie avec son icône si disponible"""
        if not obj.technology:
            return _("Non spécifiée")

        if obj.technology.image:
            return format_html('<img src="{}" style="max-height: 20px; vertical-align: middle;" /> {}',
                               obj.technology.image.url,
                               obj.technology.name)
        return obj.technology.name

    @admin.display(description=_("Nb. choix"))
    def choices_count(self, obj):
        """Affiche le nombre de choix liés à la question"""
        count = obj.choices.count()
        if count == 0:
            return format_html('<span style="color: red;">0</span>')
        return count

    @admin.display(description=_("Aperçu des choix"))
    def choices_preview(self, obj):
        """Affiche un aperçu des choix disponibles pour la question"""
        choices = obj.choices.all()
        if not choices:
            return _("Aucun choix disponible")

        html = ['<ul>']
        for choice in choices:
            status = '✅' if choice.is_correct else '❌'
            html.append(f'<li>{status} {choice.text[:100]}{"..." if len(choice.text) > 100 else ""}</li>')
        html.append('</ul>')

        return format_html(''.join(html))

    @admin.display(description=_("Marquer comme publiées"))
    def make_published(self, request, queryset):
        """Action pour marquer les questions sélectionnées comme publiées"""
        updated = queryset.update(status=Question.Status.PUBLISHED)
        self.message_user(request, _(f"{updated} question(s) ont été marquées comme publiées."))

    @admin.display(description=_("Marquer comme rejetées"))
    def make_rejected(self, request, queryset):
        """Action pour marquer les questions sélectionnées comme rejetées"""
        updated = queryset.update(status=Question.Status.REJECTED)
        self.message_user(request, _(f"{updated} question(s) ont été marquées comme rejetées."))


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'text_preview', 'is_correct', 'question_text', 'created_at']
    list_filter = ['is_correct', 'question__difficulty', 'question__status']
    search_fields = ['text', 'question__text']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('question', 'text', 'is_correct')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_("Texte"))
    def text_preview(self, obj):
        """Affiche une version tronquée du texte du choix"""
        if len(obj.text) > 50:
            return f"{obj.text[:50]}..."
        return obj.text

    @admin.display(description=_("Question"))
    def question_text(self, obj):
        """Affiche le début du texte de la question associée"""
        if obj.question:
            return format_html('<a href="{}">{}</a>',
                               reverse('admin:questions_question_change', args=[obj.question.id]),
                               obj.question.text[:50] + ('...' if len(obj.question.text) > 50 else ''))
        return _("Inconnue")
