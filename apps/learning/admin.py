import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db import models
from django.db.models import Count, Avg, Max, Q, Case, When, F, FloatField
from django.http import HttpResponse
from django.urls import reverse, path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    Course, Module, Content, Quiz, QuizQuestion, QuizChoice,
    QuizResult, QuizAnswer, Progress, Certificate
)


class InstructorFilter(SimpleListFilter):
    title = _('Instructeur')
    parameter_name = 'instructor_query'

    def lookups(self, request, model_admin):
        return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                Q(publisher__username__icontains=self.value()) |
                Q(publisher__first_name__icontains=self.value()) |
                Q(publisher__last_name__icontains=self.value())
            )
        return queryset

    def choices(self, changelist):
        # This removes the default filter choices
        yield {
            'selected': self.value() is None,
            'query_string': changelist.get_query_string({}, [self.parameter_name]),
            'display': _('All'),
        }


class CourseStatusFilter(SimpleListFilter):
    title = _('Statut du cours')
    parameter_name = 'course_status'

    def lookups(self, request, model_admin):
        return [
            ('free', _('Gratuits')),
            ('paid', _('Payants')),
            ('active', _('Actifs')),
            ('inactive', _('Inactifs')),
            ('beginner', _('Débutant')),
            ('intermediate', _('Intermédiaire')),
            ('advanced', _('Avancé')),
            ('popular', _('Populaires (>10 étudiants)')),
            ('new', _('Nouveaux (7 derniers jours)')),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'free':
            return queryset.filter(is_free=True)
        elif self.value() == 'paid':
            return queryset.filter(is_free=False)
        elif self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)
        elif self.value() in ['beginner', 'intermediate', 'advanced']:
            return queryset.filter(level=self.value())
        elif self.value() == 'popular':
            return queryset.annotate(
                student_count=Count('modules__contents__progress__user', distinct=True)
            ).filter(student_count__gt=10)
        elif self.value() == 'new':
            return queryset.filter(created_at__gte=timezone.now() - timedelta(days=7))
        return queryset


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ['title', 'description', 'order', 'is_active', 'content_count', 'has_quiz']
    readonly_fields = ['content_count', 'has_quiz']
    show_change_link = True
    ordering = ['order', 'title']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('course').prefetch_related(
            'contents', 'quiz'
        ).annotate(
            total_contents=Count('contents'),
            has_quiz_count=Count('quiz')
        )

    @admin.display(description=_('Nb contenus'))
    def content_count(self, obj):
        count = getattr(obj, 'total_contents', obj.contents.count())
        if count > 0:
            color = '#28a745' if count >= 5 else '#ffc107' if count >= 2 else '#17a2b8'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 8px; font-size: 11px;">{}</span>',
                color, count
            )
        return format_html('<span style="color: #dc3545;">0</span>')

    @admin.display(description=_('Quiz'), boolean=True)
    def has_quiz(self, obj):
        return getattr(obj, 'has_quiz_count', 0) > 0 or hasattr(obj, 'quiz')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'level_badge', 'status_badge', 'free_badge', 'instructor_info',
        'modules_count', 'total_contents_count', 'students_count',
        'display_completion_rate', 'certificates_count', 'last_activity'
    ]
    list_filter = [
        CourseStatusFilter, InstructorFilter, 'level', 'is_free', 'is_active',
        'created_at'
    ]
    search_fields = [
        'title', 'description', 'publisher__username',
        'publisher__email', 'publisher__first_name', 'publisher__last_name'
    ]
    readonly_fields = [
        'slug', 'modules_count', 'total_contents_count', 'total_quizzes_count',
        'students_count', 'certificates_count',
        'course_stats', 'engagement_metrics'
    ]
    inlines = [ModuleInline]
    list_per_page = 25

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['title', 'slug', 'description', 'level', 'publisher'],
            'classes': ['wide']
        }),
        (_('Configuration'), {
            'fields': [
                'is_free', 'is_active', 'estimated_duration'
            ],
            'classes': ['collapse']
        }),
        (_('Statistiques générales'), {
            'fields': [
                'modules_count', 'total_contents_count', 'total_quizzes_count',
                'students_count', 'certificates_count'
            ],
            'classes': ['collapse']
        }),
        (_('Analyses avancées'), {
            'fields': ['course_stats', 'engagement_metrics'],
            'classes': ['collapse']
        })
    ]

    actions = [
        'make_free', 'make_paid', 'activate_courses', 'deactivate_courses',
        'generate_certificates', 'export_analytics'
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'publisher'
        ).prefetch_related(
            'modules', 'modules__contents', 'modules__quiz',
            'certificate_set'
        ).annotate(
            modules_total=Count('modules', distinct=True),
            total_contents_agg=Count('modules__contents', distinct=True),
            total_quizzes_agg=Count('modules__quiz', distinct=True),
            students_total=Count('modules__contents__progress__user', distinct=True),
            certificates_total=Count('certificate', distinct=True),
            last_progress=Max('modules__contents__progress__last_accessed'),
            completion_rate_agg=Case(
                When(students_total__gt=0, then=(F('certificates_total') * 100.0 / F('students_total'))),
                default=0.0,
                output_field=FloatField()
            )
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-analytics/',
                 self.admin_site.admin_view(self.export_analytics_view),
                 name='learning_course_export_analytics'),
        ]
        return custom_urls + urls

    def export_analytics_view(self, request):
        """Export CSV des analytics de tous les cours"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="course_analytics.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Cours', 'Niveau', 'Gratuit', 'Actif', 'Modules', 'Contenus',
            'Étudiants', 'Taux complétion', 'Certificats'
        ])

        for course in self.get_queryset(request):
            writer.writerow([
                course.title,
                course.get_level_display(),
                'Oui' if course.is_free else 'Non',
                'Oui' if course.is_active else 'Non',
                getattr(course, 'modules_total', 0),
                getattr(course, 'total_contents_agg', 0),
                getattr(course, 'students_total', 0),
                f"{getattr(course, 'completion_rate_agg', 0.0):.1f}%",
                getattr(course, 'certificates_total', 0),
            ])

        return response

    @admin.display(description=_('Quizzes'))
    def total_quizzes_count(self, obj):
        count = getattr(obj, 'total_quizzes_agg', 0)
        if count > 0:
            url = reverse('admin:learning_quiz_changelist') + f'?module__course__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, count
            )
        return 0

    @admin.display(description=_('Niveau'), ordering='level')
    def level_badge(self, obj):
        colors = {
            'beginner': '#28a745',
            'intermediate': '#ffc107',
            'advanced': '#dc3545'
        }
        labels = {
            'beginner': 'Débutant',
            'intermediate': 'Intermédiaire',
            'advanced': 'Avancé'
        }
        color = colors.get(obj.level, '#6c757d')
        label = labels.get(obj.level, obj.level)

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, label
        )

    @admin.display(description=_('Statut'), ordering='is_active')
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">✓ Actif</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">✗ Inactif</span>'
        )

    @admin.display(description=_('Type'))
    def free_badge(self, obj):
        if obj.is_free:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">Gratuit</span>'
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">Payant</span>'
        )

    @admin.display(description=_('Instructeur'))
    def instructor_info(self, obj):
        if obj.publisher:
            name = obj.publisher.get_full_name() or obj.publisher.username
            return format_html(
                '<div><strong>{}</strong><br><small style="color: #6c757d;">{}</small></div>',
                name, obj.publisher.email
            )
        return format_html('<em style="color: #dc3545;">Non assigné</em>')

    @admin.display(description=_('Modules'), ordering='modules_total')
    def modules_count(self, obj):
        count = getattr(obj, 'modules_total', 0)
        if count > 0:
            url = reverse('admin:learning_module_changelist') + f'?course__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690; font-weight: bold;">{}</a>',
                url, count
            )
        return 0

    @admin.display(description=_('Contenus'), ordering='total_contents_agg')
    def total_contents_count(self, obj):
        count = getattr(obj, 'total_contents_agg', 0)
        if count > 0:
            url = reverse('admin:learning_content_changelist') + f'?module__course__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, count
            )
        return 0

    @admin.display(description=_('Étudiants'), ordering='students_total')
    def students_count(self, obj):
        count = getattr(obj, 'students_total', 0)
        if count > 0:
            return format_html(
                '<span style="background-color: #17a2b8; color: white; padding: 2px 6px; border-radius: 8px; font-size: 11px;">{}</span>',
                count
            )
        return 0

    @admin.display(description=_('Dernière activité'))
    def last_activity(self, obj):
        last_progress_date = getattr(obj, 'last_progress', None)
        if not last_progress_date:
            return format_html('<span style="color: #6c757d;">Aucune</span>')

        days_ago = (timezone.now() - last_progress_date).days
        color = '#28a745' if days_ago <= 7 else '#ffc107' if days_ago <= 30 else '#dc3545'
        return format_html('<span style="color: {};">Il y a {} jour(s)</span>', color, days_ago)

    def _calculate_completion_rate(self, obj):
        """Calcul optimisé du taux de complétion"""
        return getattr(obj, 'completion_rate_agg', 0.0)

    @admin.display(description=_('Taux de complétion'), ordering='completion_rate_agg')
    def display_completion_rate(self, obj):
        rate = self._calculate_completion_rate(obj)
        # Forcer la conversion en float pour éviter toute ambiguïté de type.
        rate_as_float = float(rate)
        color = '#28a745' if rate_as_float >= 80 else '#ffc107' if rate_as_float >= 50 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, rate_as_float
        )

    @admin.display(description=_('Certificats'), ordering='certificates_total')
    def certificates_count(self, obj):
        count = getattr(obj, 'certificates_total', 0)
        if count > 0:
            url = reverse('admin:learning_certificate_changelist') + f'?course__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #28a745; font-weight: bold;">🏆 {}</a>',
                url, count
            )
        return 0

    @admin.display(description=_('Statistiques détaillées'))
    def course_stats(self, obj):
        total_contents = getattr(obj, 'total_contents_agg', 0)

        progress_stats = Progress.objects.filter(content__module__course=obj).aggregate(
            total_progress=Count('id'),
            completed_progress=Count('id', filter=Q(is_completed=True))
        )
        total_progress = progress_stats.get('total_progress', 0)
        completed_progress = progress_stats.get('completed_progress', 0)

        avg_score = QuizResult.objects.filter(
            quiz__module__course=obj
        ).aggregate(avg=Avg('score'))['avg'] or 0.0
        return format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
            '<strong>Analyse du cours:</strong><br>'
            '• Contenus totaux: {}<br>'
            '• Progrès enregistrés: {}<br>'
            '• Completions: {} ({:.1f}%)<br>'
            '• Score moyen quiz: {:.1f}%<br>'
            '</div>',
            total_contents,
            total_progress,
            completed_progress,
            (completed_progress / total_progress * 100) if total_progress > 0 else 0,
            avg_score
        )

    @admin.display(description=_('Métriques d\'engagement'))
    def engagement_metrics(self, obj):
        total_contents = getattr(obj, 'total_contents_agg', 0)
        students_total = getattr(obj, 'students_total', 0)

        if students_total > 0 and total_contents > 0:
            total_progress = Progress.objects.filter(content__module__course=obj).count()
            engagement_rate = (total_progress / (students_total * total_contents)) * 100

            color = '#28a745' if engagement_rate >= 80 else '#ffc107' if engagement_rate >= 50 else '#dc3545'

            return format_html(
                '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
                '<strong>Engagement:</strong><br>'
                '• Taux: <span style="color: {}; font-weight: bold;">{:.1f}%</span><br>'
                '• Interactions: {}<br>'
                '</div>',
                color, engagement_rate, total_progress
            )

        return format_html('<em style="color: #6c757d;">Données insuffisantes</em>')

    @admin.action(description=_('Rendre gratuit'))
    def make_free(self, request, queryset):
        try:
            updated = queryset.update(is_free=True)
            self.message_user(
                request,
                f"{updated} cours rendu(s) gratuit(s) avec succès.",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Erreur lors de la modification: {str(e)}",
                messages.ERROR
            )

    @admin.action(description=_('Rendre payant'))
    def make_paid(self, request, queryset):
        try:
            updated = queryset.update(is_free=False)
            self.message_user(
                request,
                f"{updated} cours rendu(s) payant(s) avec succès.",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Erreur lors de la modification: {str(e)}",
                messages.ERROR
            )

    @admin.action(description=_('Activer les cours sélectionnés'))
    def activate_courses(self, request, queryset):
        try:
            updated = queryset.update(is_active=True)
            self.message_user(
                request,
                f"{updated} cours activé(s) avec succès.",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Erreur lors de l'activation: {str(e)}",
                messages.ERROR
            )

    @admin.action(description=_('Désactiver les cours sélectionnés'))
    def deactivate_courses(self, request, queryset):
        try:
            updated = queryset.update(is_active=False)
            self.message_user(
                request,
                f"{updated} cours désactivé(s) avec succès.",
                messages.WARNING
            )
        except Exception as e:
            self.message_user(
                request,
                f"Erreur lors de la désactivation: {str(e)}",
                messages.ERROR
            )

    @admin.action(description=_('Générer certificats automatiquement'))
    def generate_certificates(self, request, queryset):
        generated = 0
        errors = 0

        for course in queryset:
            try:
                total_contents = Content.objects.filter(module__course=course).count()

                if total_contents > 0:
                    eligible_users = Progress.objects.filter(
                        content__module__course=course,
                        is_completed=True
                    ).values('user').annotate(
                        completed_count=Count('id')
                    ).filter(completed_count=total_contents).values_list('user', flat=True)

                    for user_id in eligible_users:
                        certificate, created = Certificate.objects.get_or_create(
                            user_id=user_id,
                            course=course
                        )
                        if created:
                            generated += 1
            except Exception as e:
                errors += 1
                continue

        if generated > 0:
            self.message_user(
                request,
                f"{generated} certificat(s) généré(s) automatiquement.",
                messages.SUCCESS
            )
        if errors > 0:
            self.message_user(
                request,
                f"{errors} erreur(s) lors de la génération des certificats.",
                messages.WARNING
            )

    @admin.action(description=_('Exporter les analytics'))
    def export_analytics(self, request, queryset):
        return self.export_analytics_view(request)


class ContentInline(admin.TabularInline):
    model = Content
    extra = 0
    fields = ['title', 'content_type', 'content_preview', 'progress_count']
    readonly_fields = ['content_preview', 'progress_count']
    show_change_link = True

    @admin.display(description=_('Aperçu'))
    def content_preview(self, obj):
        if obj.content_type == 'markdown' and obj.content:
            preview = obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
            return format_html('<em>{}</em>', preview)
        elif obj.resource_url:
            return format_html('<a href="{}" target="_blank">🔗 Lien</a>', obj.resource_url)
        elif obj.resource_file:
            return format_html('📁 Fichier')
        return '-'

    @admin.display(description=_('Progrès'))
    def progress_count(self, obj):
        if obj.pk:
            completed = Progress.objects.filter(content=obj, is_completed=True).count()
            total = Progress.objects.filter(content=obj).count()
            if total > 0:
                return format_html('{}/{} ({}%)', completed, total, int(completed / total * 100))
        return '0/0'


class QuizInline(admin.StackedInline):
    model = Quiz
    extra = 0
    fields = ['title', 'description', 'questions_count', 'avg_score']
    readonly_fields = ['questions_count', 'avg_score']
    show_change_link = True

    @admin.display(description=_('Questions'))
    def questions_count(self, obj):
        if obj.pk:
            count = obj.questions.count()
            return format_html(
                '<span style="background-color: #17a2b8; color: white; padding: 2px 6px; border-radius: 8px;">{}</span>',
                count
            )
        return 0

    @admin.display(description=_('Score moyen'))
    def avg_score(self, obj):
        if obj.pk:
            avg = QuizResult.objects.filter(quiz=obj).aggregate(avg=Avg('score'))['avg']
            if avg:
                return f"{avg:.1f}%"
        return "N/A"


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'course_link', 'contents_count', 'quiz_status',
        'students_count', 'completion_rate'
    ]
    list_filter = ['course', 'course__level']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['contents_count', 'students_count', 'completion_rate']
    inlines = [ContentInline, QuizInline]

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['course', 'title', 'description']
        }),
        (_('Statistiques'), {
            'fields': ['contents_count', 'students_count', 'completion_rate'],
            'classes': ['collapse']
        })
    ]

    @admin.display(description=_('Cours'), ordering='course__title')
    def course_link(self, obj):
        url = reverse('admin:learning_course_change', args=[obj.course.pk])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a>',
            url, obj.course.title
        )

    @admin.display(description=_('Contenus'))
    def contents_count(self, obj):
        count = obj.contents.count()
        if count > 0:
            url = reverse('admin:learning_content_changelist') + f'?module__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, count
            )
        return 0

    @admin.display(description=_('Quiz'), boolean=True)
    def quiz_status(self, obj):
        return hasattr(obj, 'quiz') and obj.quiz is not None

    @admin.display(description=_('Étudiants'))
    def students_count(self, obj):
        count = Progress.objects.filter(content__module=obj).values('user').distinct().count()
        return count

    @admin.display(description=_('Taux de complétion'))
    def completion_rate(self, obj):
        total_contents = obj.contents.count()
        if total_contents == 0:
            return "N/A"

        users_in_module_qs = Progress.objects.filter(content__module=obj).values('user').distinct()
        users_in_module_count = users_in_module_qs.count()

        if users_in_module_count == 0:
            return "0%"

        completed_users_count = Progress.objects.filter(
            content__module=obj, is_completed=True
        ).values('user').annotate(
            completed_contents=Count('content', distinct=True)
        ).filter(completed_contents=total_contents).count()

        rate = (completed_users_count / users_in_module_count) * 100
        color = '#28a745' if rate >= 80 else '#ffc107' if rate >= 50 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'module_link', 'content_type_badge', 'content_preview',
        'progress_stats', 'completion_rate'
    ]
    list_filter = ['content_type', 'module__course', 'module']
    search_fields = ['title', 'module__title', 'module__course__title']
    readonly_fields = ['progress_stats', 'completion_rate', 'content_analysis']

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['module', 'title', 'content_type']
        }),
        (_('Contenu'), {
            'fields': ['resource_file', 'resource_url', 'content'],
            'description': _('Selon le type de contenu, utilisez le champ approprié.')
        }),
        (_('Statistiques'), {
            'fields': ['progress_stats', 'completion_rate', 'content_analysis'],
            'classes': ['collapse']
        })
    ]

    @admin.display(description=_('Module'), ordering='module__title')
    def module_link(self, obj):
        url = reverse('admin:learning_module_change', args=[obj.module.pk])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a>',
            url, f"{obj.module.course.title} - {obj.module.title}"
        )

    @admin.display(description=_('Content Type'), ordering='content_type')
    def content_type_badge(self, obj):
        colors = {
            'video': '#dc3545',
            'pdf': '#28a745',
            'talk': '#ffc107',
            'external': '#17a2b8',
            'markdown': '#6f42c1'
        }
        icons = {
            'video': '🎥',
            'pdf': '📄',
            'talk': '🎤',
            'external': '🔗',
            'markdown': '📝'
        }

        color = colors.get(obj.content_type, '#6c757d')
        icon = icons.get(obj.content_type, '📄')

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{} {}</span>',
            color, icon, obj.get_content_type_display()
        )

    @admin.display(description=_('Aperçu'))
    def content_preview(self, obj):
        if obj.content_type == 'markdown' and obj.content:
            preview = obj.content[:30] + '...' if len(obj.content) > 30 else obj.content
            return format_html('<small style="color: #6c757d;"><em>{}</em></small>', preview)
        elif obj.resource_url:
            return format_html('<a href="{}" target="_blank" style="font-size: 12px;">🔗 Ouvrir</a>', obj.resource_url)
        elif obj.resource_file:
            return format_html('<span style="font-size: 12px;">📁 {}</span>', obj.resource_file.name.split('/')[-1])
        return '-'

    @admin.display(description=_('Statistiques'))
    def progress_stats(self, obj):
        completed = Progress.objects.filter(content=obj, is_completed=True).count()
        total = Progress.objects.filter(content=obj).count()

        if total == 0:
            return "Aucun étudiant"

        rate = (completed / total) * 100
        return format_html(
            '<div style="font-size: 12px;">'
            'Terminé: {}/{} ({}%)'
            '</div>',
            completed, total, int(rate)
        )

    @admin.display(description=_('Taux de complétion'))
    def completion_rate(self, obj):
        completed = Progress.objects.filter(content=obj, is_completed=True).count()
        total = Progress.objects.filter(content=obj).count()

        if total == 0:
            return "0%"

        rate = (completed / total) * 100
        color = '#28a745' if rate >= 80 else '#ffc107' if rate >= 50 else '#dc3545'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, rate
        )

    @admin.display(description=_('Analyse détaillée'))
    def content_analysis(self, obj):
        progress_data = Progress.objects.filter(content=obj)
        completed_count = progress_data.filter(is_completed=True).count()
        total_count = progress_data.count()

        recent_completions = progress_data.filter(
            is_completed=True,
            completed_at__gte=timezone.now() - timedelta(days=7)
        ).count()

        return format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
            '<strong>Analyse du contenu:</strong><br>'
            '• Étudiants total: {}<br>'
            '• Complétions: {} ({:.1f}%)<br>'
            '• Complétions récentes (7j): {}<br>'
            '</div>',
            total_count,
            completed_count,
            (completed_count / total_count * 100) if total_count > 0 else 0,
            recent_completions
        )


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 0
    fields = ['title', 'description', 'explanation', 'choices_count', 'correct_answers']
    readonly_fields = ['choices_count', 'correct_answers']
    show_change_link = True

    @admin.display(description=_('Choix'))
    def choices_count(self, obj):
        if obj.pk:
            return obj.choices.count()
        return 0

    @admin.display(description=_('Bonnes réponses'))
    def correct_answers(self, obj):
        if obj.pk:
            return obj.choices.filter(is_correct=True).count()
        return 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'module_link', 'questions_count', 'attempts_count',
        'average_score', 'success_rate'
    ]
    list_filter = ['module__course', 'module']
    search_fields = ['title', 'description', 'module__title']
    readonly_fields = ['questions_count', 'attempts_count', 'average_score', 'success_rate', 'quiz_analytics']
    inlines = [QuizQuestionInline]

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['module', 'title', 'description']
        }),
        (_('Statistiques'), {
            'fields': ['questions_count', 'attempts_count', 'average_score', 'success_rate'],
            'classes': ['collapse']
        }),
        (_('Analyse détaillée'), {
            'fields': ['quiz_analytics'],
            'classes': ['collapse']
        })
    ]

    @admin.display(description=_('Module'), ordering='module__title')
    def module_link(self, obj):
        url = reverse('admin:learning_module_change', args=[obj.module.pk])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a>',
            url, f"{obj.module.course.title} - {obj.module.title}"
        )

    @admin.display(description=_('Questions'))
    def questions_count(self, obj):
        count = obj.questions.count()
        if count > 0:
            url = reverse('admin:learning_quizquestion_changelist') + f'?quiz__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, count
            )
        return 0

    @admin.display(description=_('Tentatives'))
    def attempts_count(self, obj):
        count = QuizResult.objects.filter(quiz=obj).count()
        if count > 0:
            url = reverse('admin:learning_quizresult_changelist') + f'?quiz__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, count
            )
        return 0

    @admin.display(description=_('Score moyen'))
    def average_score(self, obj):
        avg = QuizResult.objects.filter(quiz=obj).aggregate(avg=Avg('score'))['avg']
        if avg:
            color = '#28a745' if avg >= 80 else '#ffc107' if avg >= 60 else '#dc3545'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color, avg
            )
        return "N/A"

    @admin.display(description=_('Taux de réussite'))
    def success_rate(self, obj):
        results_qs = QuizResult.objects.filter(quiz=obj)
        total_attempts = results_qs.count()
        if total_attempts == 0:
            return "N/A"

        # We'll consider a score of 80 as passing for this calculation.
        successful_attempts = results_qs.filter(score__gte=80).count()
        rate = (successful_attempts / total_attempts) * 100

        color = '#28a745' if rate >= 80 else '#ffc107' if rate >= 60 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )

    @admin.display(description=_('Analyse du quiz'))
    def quiz_analytics(self, obj):
        results = QuizResult.objects.filter(quiz=obj)
        if not results:
            return "Aucune donnée"

        total_attempts = results.count()
        avg_score = results.aggregate(avg=Avg('score'))['avg'] or 0
        best_score = results.aggregate(max=models.Max('score'))['max'] or 0
        worst_score = results.aggregate(min=models.Min('score'))['min'] or 0

        return format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
            '<strong>Analyse du quiz:</strong><br>'
            '• Tentatives totales: {}<br>'
            '• Score moyen: {:.1f}%<br>'
            '• Meilleur score: {:.1f}%<br>'
            '• Score le plus bas: {:.1f}%<br>'
            '</div>',
            total_attempts, avg_score, best_score, worst_score
        )


class QuizChoiceInline(admin.TabularInline):
    model = QuizChoice
    extra = 2
    fields = ['text', 'is_correct']


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['title', 'quiz_link', 'description_preview', 'explanation_preview',
                    'choices_count', 'correct_choices', 'success_rate']
    list_filter = ['quiz__module__course', 'quiz']
    search_fields = ['title', 'description', 'explanation', 'quiz__title']
    readonly_fields = ['choices_count', 'correct_choices', 'success_rate']
    inlines = [QuizChoiceInline]

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['quiz', 'title']
        }),
        (_('Contenu'), {
            'fields': ['description', 'explanation']
        }),
        (_('Statistiques'), {
            'fields': ['choices_count', 'correct_choices', 'success_rate'],
            'classes': ['collapse']
        })
    ]

    @admin.display(description=_('Quiz'), ordering='quiz__title')
    def quiz_link(self, obj):
        url = reverse('admin:learning_quiz_change', args=[obj.quiz.pk])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a>',
            url, obj.quiz.title
        )

    @admin.display(description=_('Description'))
    def description_preview(self, obj):
        if obj.description:
            preview = obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
            return format_html('<small style="color: #6c757d;">{}</small>', preview)
        return '-'

    @admin.display(description=_('Explication'))
    def explanation_preview(self, obj):
        if obj.explanation:
            preview = obj.explanation[:40] + '...' if len(obj.explanation) > 40 else obj.explanation
            return format_html('<small style="color: #28a745;">{}</small>', preview)
        return '-'

    @admin.display(description=_('Choix'))
    def choices_count(self, obj):
        return obj.choices.count()

    @admin.display(description=_('Bonnes réponses'))
    def correct_choices(self, obj):
        return obj.choices.filter(is_correct=True).count()

    @admin.display(description=_('Taux de réussite'))
    def success_rate(self, obj):
        answers = QuizAnswer.objects.filter(question=obj)
        if not answers:
            return "N/A"

        correct = answers.filter(is_correct=True).count()
        total = answers.count()
        rate = (correct / total) * 100

        color = '#28a745' if rate >= 80 else '#ffc107' if rate >= 60 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )


@admin.register(QuizChoice)
class QuizChoiceAdmin(admin.ModelAdmin):
    list_display = ['text_preview', 'question_link', 'is_correct_badge', 'selection_rate']
    list_filter = ['is_correct', 'question__quiz__module__course']
    search_fields = ['text', 'question__title']
    readonly_fields = ['selection_rate']

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['question', 'text', 'is_correct']
        }),
        (_('Statistiques'), {
            'fields': ['selection_rate'],
            'classes': ['collapse']
        })
    ]

    @admin.display(description=_('Texte'))
    def text_preview(self, obj):
        preview = obj.text[:60] + '...' if len(obj.text) > 60 else obj.text
        return preview

    @admin.display(description=_('Question'), ordering='question__title')
    def question_link(self, obj):
        url = reverse('admin:learning_quizquestion_change', args=[obj.question.pk])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a>',
            url, obj.question.title[:50]
        )

    @admin.display(description=_('Correct'), boolean=True)
    def is_correct_badge(self, obj):
        return obj.is_correct

    @admin.display(description=_('Taux de sélection'))
    def selection_rate(self, obj):
        total_answers = QuizAnswer.objects.filter(
            selected_choices=obj
        ).count()

        if total_answers == 0:
            return "N/A"

        total_attempts = QuizAnswer.objects.filter(
            question=obj.question
        ).count()

        if total_attempts == 0:
            return "N/A"

        rate = (total_answers / total_attempts) * 100
        color = '#28a745' if obj.is_correct else '#dc3545'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )


class QuizAnswerInline(admin.TabularInline):
    model = QuizAnswer
    extra = 0
    fields = ['question', 'selected_choices_preview', 'is_correct']
    readonly_fields = ['selected_choices_preview', 'is_correct']
    can_delete = False

    @admin.display(description=_('Choix sélectionnés'))
    def selected_choices_preview(self, obj):
        if obj.pk:
            choices = obj.selected_choices.all()[:3]
            return ', '.join([choice.text[:20] for choice in choices])
        return '-'

    def has_add_permission(self, request, obj=None):
        return False


class ScoreRangeFilter(SimpleListFilter):
    title = _('Tranche de score')
    parameter_name = 'score_range'

    def lookups(self, request, model_admin):
        return (
            ('failed', _('Échec')),
            ('passed', _('Réussi (score < 90%)')),
            ('excellent', _('Excellent (score >= 90%)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'failed':
            return queryset.filter(is_passed=False)
        if self.value() == 'passed':
            return queryset.filter(is_passed=True, score__lt=90)
        if self.value() == 'excellent':
            return queryset.filter(is_passed=True, score__gte=90)
        return queryset


@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'quiz_link', 'score_badge', 'passed_status',
        'attempt_number', 'duration_display', 'submitted_at'
    ]
    list_filter = [
        ScoreRangeFilter, 'is_passed', 'quiz__module__course', 'quiz',
        'submitted_at', 'attempt_number'
    ]
    search_fields = ['user__username', 'user__email', 'quiz__title']
    readonly_fields = [
        'score', 'started_at', 'submitted_at', 'is_passed', 'time_taken_seconds',
        'total_points', 'obtained_points', 'answers_count', 'detailed_results'
    ]
    date_hierarchy = 'submitted_at'
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'quiz', 'quiz__module', 'quiz__module__course'
        ).prefetch_related('answers', 'answers__selected_choices')

    @admin.display(description=_('Utilisateur'), ordering='user__username')
    def user_link(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.user.get_full_name() or obj.user.username,
            obj.user.email
        )

    @admin.display(description=_('Quiz'), ordering='quiz__title')
    def quiz_link(self, obj):
        url = reverse('admin:learning_quiz_change', args=[obj.quiz.pk])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a>',
            url, obj.quiz.title
        )

    @admin.display(description=_('Score'), ordering='score')
    def score_badge(self, obj):
        color = '#28a745' if obj.score >= 80 else '#ffc107' if obj.score >= 60 else '#dc3545'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-weight: bold;">{:.1f}%</span>',
            color, obj.score
        )

    @admin.display(description=_('Réussi'), boolean=True)
    def passed_status(self, obj):
        return obj.is_passed

    @admin.display(description=_('Durée'))
    def duration_display(self, obj):
        return obj.duration_formatted

    @admin.display(description=_('Réponses'))
    def answers_count(self, obj):
        correct = obj.answers.filter(is_correct=True).count()
        total = obj.answers.count()
        return f"{correct}/{total}"

    @admin.display(description=_('Détails des réponses'))
    def detailed_results(self, obj):
        html = '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
        for answer in obj.answers.all()[:5]:
            status_icon = '✅' if answer.is_correct else '❌'
            html += f'<div style="margin-bottom: 5px;">'
            html += f'{status_icon} <strong>{answer.question.title[:50]}</strong><br>'
            choices_text = ", ".join([choice.text[:20] for choice in answer.selected_choices.all()])
            html += f'<small>Choix: {choices_text}</small>'
            html += '</div>'
        if obj.answers.count() > 5:
            html += f'<small>... et {obj.answers.count() - 5} autres réponses</small>'
        html += '</div>'
        return format_html(html)


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'content_link', 'is_completed_badge',
        'progress_percentage', 'last_accessed', 'course_info'
    ]
    list_filter = [
        'is_completed', 'content__module__course', 'content__module',
        'content__content_type', 'completed_at', 'last_accessed'
    ]
    search_fields = [
        'user__username', 'user__email', 'content__title',
        'content__module__title', 'content__module__course__title'
    ]
    readonly_fields = ['started_at', 'completed_at', 'last_accessed', 'time_spent_display']
    date_hierarchy = 'last_accessed'

    actions = ['mark_completed', 'mark_incomplete']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'content', 'content__module', 'content__module__course'
        )

    @admin.display(description=_('Utilisateur'), ordering='user__username')
    def user_link(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.user.get_full_name() or obj.user.username,
            obj.user.email
        )

    @admin.display(description=_('Contenu'), ordering='content__title')
    def content_link(self, obj):
        url = reverse('admin:learning_content_change', args=[obj.content.pk])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a><br>'
            '<small style="color: #6c757d;">{}</small>',
            url, obj.content.title, obj.content.get_content_type_display()
        )

    @admin.display(description=_('Statut'), boolean=True, ordering='is_completed')
    def is_completed_badge(self, obj):
        return obj.is_completed

    @admin.display(description=_('Progression'))
    def progress_percentage(self, obj):
        if obj.is_completed:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">100%</span>'
            )
        else:
            if obj.content.duration_minutes and obj.time_spent_seconds:
                estimated_seconds = obj.content.duration_minutes * 60
                percentage = min((obj.time_spent_seconds / estimated_seconds) * 100, 99)
                color = '#ffc107' if percentage >= 50 else '#17a2b8'
                return format_html(
                    '<span style="color: {}; font-weight: bold;">{:.0f}%</span>',
                    color, percentage
                )
        return "0%"

    @admin.display(description=_('Cours'))
    def course_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.content.module.course.title,
            obj.content.module.title
        )

    @admin.display(description=_('Temps passé'))
    def time_spent_display(self, obj):
        if obj.time_spent_seconds:
            hours = obj.time_spent_seconds // 3600
            minutes = (obj.time_spent_seconds % 3600) // 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "0m"

    @admin.action(description=_('Marquer comme terminé'))
    def mark_completed(self, request, queryset):
        try:
            updated = queryset.update(is_completed=True, completed_at=timezone.now())
            self.message_user(
                request,
                f"{updated} progrès marqué(s) comme terminé(s).",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Erreur: {str(e)}",
                messages.ERROR
            )

    @admin.action(description=_('Marquer comme non terminé'))
    def mark_incomplete(self, request, queryset):
        try:
            updated = queryset.update(is_completed=False, completed_at=None)
            self.message_user(
                request,
                f"{updated} progrès marqué(s) comme non terminé(s).",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Erreur: {str(e)}",
                messages.ERROR
            )


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'course_link', 'issued_at', 'file_link',
        'course_completion_stats'
    ]
    list_filter = ['course', 'issued_at']
    search_fields = ['user__username', 'user__email', 'course__title']
    readonly_fields = ['issued_at', 'course_completion_stats', 'user_progress_summary']
    date_hierarchy = 'issued_at'

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['user', 'course', 'issued_at']
        }),
        (_('Fichier'), {
            'fields': ['file']
        }),
        (_('Statistiques'), {
            'fields': ['course_completion_stats', 'user_progress_summary'],
            'classes': ['collapse']
        })
    ]

    @admin.display(description=_('Utilisateur'), ordering='user__username')
    def user_link(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.user.get_full_name() or obj.user.username,
            obj.user.email
        )

    @admin.display(description=_('Cours'), ordering='course__title')
    def course_link(self, obj):
        url = reverse('admin:learning_course_change', args=[obj.course.pk])
        return format_html(
            '<a href="{}" style="color: #417690; font-weight: bold;">{}</a>',
            url, obj.course.title
        )

    @admin.display(description=_('Fichier'))
    def file_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank" style="color: #28a745;">📄 Télécharger</a>',
                obj.file.url
            )
        return "Non disponible"

    @admin.display(description=_('Statistiques du cours'))
    def course_completion_stats(self, obj):
        total_contents = Content.objects.filter(module__course=obj.course).count()
        completed_by_user = Progress.objects.filter(
            content__module__course=obj.course,
            user=obj.user,
            is_completed=True
        ).count()

        return format_html(
            '<div style="padding: 5px; background-color: #e8f5e8; border-radius: 3px;">'
            'Contenus complétés: {}/{} (100%)'
            '</div>',
            completed_by_user, total_contents
        )

    @admin.display(description=_('Résumé de progression'))
    def user_progress_summary(self, obj):
        quiz_results = QuizResult.objects.filter(
            quiz__module__course=obj.course,
            user=obj.user
        )

        if quiz_results:
            avg_score = quiz_results.aggregate(avg=Avg('score'))['avg']
            quiz_count = quiz_results.count()
        else:
            avg_score = 0
            quiz_count = 0

        return format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
            '<strong>Résumé de progression:</strong><br>'
            '• Quiz complétés: {}<br>'
            '• Score moyen: {:.1f}%<br>'
            '• Certificat émis: {}<br>'
            '</div>',
            quiz_count,
            avg_score,
            obj.issued_at.strftime('%d/%m/%Y à %H:%M')
        )
