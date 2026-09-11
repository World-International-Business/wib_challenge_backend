from datetime import timedelta

from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Organization, Notification, UserNotification


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_link', 'sector', 'company_size_badge', 'city', 'country',
                    'jobs_count', 'logo_preview', 'created_at')
    list_display_links = ('name',)
    list_filter = ('country', 'city', 'company_size', 'sector', 'created_at')
    search_fields = ('name', 'account__email', 'sector', 'city', 'country', 'neighborhood')
    readonly_fields = ('created_at', 'updated_at', 'logo_preview', 'org_stats')
    list_per_page = 25

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('name', 'description', 'account', 'sector', 'company_size')
        }),
        (_('Contact'), {
            'fields': ('email', 'phone', 'website')
        }),
        (_('Localisation'), {
            'fields': ('country', 'city', 'neighborhood')
        }),
        (_('Médias'), {
            'fields': ('logo', 'logo_preview')
        }),
        (_('Statistiques'), {
            'fields': ('org_stats',),
            'classes': ('collapse',)
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('account')

    @admin.display(description=_('Compte'), ordering='account__email')
    def account_link(self, obj):
        if obj.account:
            url = reverse('admin:accounts_user_change', args=[obj.account.pk])
            return format_html('<a href="{}" style="color: #417690;">{}</a>', url, obj.account.email)
        return '-'

    @admin.display(description=_('Taille'))
    def company_size_badge(self, obj):
        if not obj.company_size:
            return '-'
        colors = {
            'micro': '#6c757d',
            'small': '#17a2b8',
            'medium': '#ffc107',
            'large': '#fd7e14',
            'enterprise': '#dc3545',
        }
        color = colors.get(obj.company_size, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 11px;">{}</span>',
            color, obj.get_company_size_display()
        )

    @admin.display(description=_('Logo'))
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 50px; border-radius: 4px;" />', obj.logo.url)
        return _('Aucun logo')

    @admin.display(description=_('Offres d\'emploi'))
    def jobs_count(self, obj):
        try:
            count = obj.account.joboffer_set.count() if hasattr(obj.account, 'joboffer_set') else 0
        except Exception:
            count = 0
        if count > 0:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 2px 6px; '
                'border-radius: 8px; font-size: 11px;">{}</span>',
                count
            )
        return '0'

    @admin.display(description=_('Statistiques organisation'))
    def org_stats(self, obj):
        stats = []
        stats.append(f'<strong>Organisation:</strong> {obj.name}')
        if obj.email:
            stats.append(f'• Email: {obj.email}')
        if obj.website:
            stats.append(f'• Site web: {obj.website}')
        stats.append(f'• Créée le: {obj.created_at.strftime("%d/%m/%Y")}')
        return format_html('<br>'.join(stats))

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['total_organizations'] = Organization.objects.count()
        return super().changelist_view(request, extra_context=extra_context)


class NotificationTypeFilter(admin.SimpleListFilter):
    title = _('Type de notification')
    parameter_name = 'notification_type'

    def lookups(self, request, model_admin):
        return Notification.Types.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())
        return queryset


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'type_badge', 'title', 'organization_link', 'is_read_badge',
                    'related_application_link', 'related_evaluation_link', 'created_at']
    list_display_links = ['id', 'title']
    list_filter = [NotificationTypeFilter, 'is_read', 'created_at', 'organization']
    search_fields = ['title', 'message', 'organization__name']
    readonly_fields = ['created_at', 'is_read_badge']
    list_per_page = 25
    actions = ['mark_as_read', 'mark_as_unread']

    fieldsets = (
        (_('📧 Notification'), {
            'fields': ('organization', 'type', 'title', 'message')
        }),
        (_('🔗 Relations'), {
            'fields': ('related_application', 'related_evaluation'),
            'classes': ('collapse',)
        }),
        (_('📊 Statut'), {
            'fields': ('is_read', 'is_read_badge')
        }),
        (_('📅 Métadonnées'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_('Type'))
    def type_badge(self, obj):
        colors = {
            Notification.Types.INTERVIEW_REMINDER: '#ffc107',
            Notification.Types.TEST_COMPLETED: '#28a745',
            Notification.Types.NEW_APPLICATION: '#17a2b8',
            Notification.Types.CONTRACT_SENT: '#6f42c1',
            Notification.Types.CONTRACT_SIGNED: '#28a745',
        }
        color = colors.get(obj.type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 11px;">{}</span>',
            color, obj.get_type_display()
        )

    @admin.display(description=_('Organisation'))
    def organization_link(self, obj):
        if obj.organization:
            url = reverse('admin:organizations_organization_change', args=[obj.organization.pk])
            return format_html('<a href="{}" style="color: #417690;">{}</a>', url, obj.organization.name)
        return '-'

    @admin.display(description=_('Lu'), boolean=True)
    def is_read_badge(self, obj):
        return obj.is_read

    @admin.display(description=_('Candidature'))
    def related_application_link(self, obj):
        if obj.related_application:
            url = reverse('admin:jobs_jobapplication_change', args=[obj.related_application.pk])
            return format_html('<a href="{}">#{}</a>', url, obj.related_application.pk)
        return '-'

    @admin.display(description=_('Évaluation'))
    def related_evaluation_link(self, obj):
        if obj.related_evaluation:
            url = reverse('admin:evaluations_evaluation_change', args=[obj.related_evaluation.pk])
            return format_html('<a href="{}">{}</a>', url, obj.related_evaluation.title[:30])
        return '-'

    @admin.action(description=_('Marquer comme lues'))
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notification(s) marquée(s) comme lue(s).')

    @admin.action(description=_('Marquer comme non lues'))
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notification(s) marquée(s) comme non lue(s).')

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['total_notifications'] = Notification.objects.count()
        extra_context['unread_notifications'] = Notification.objects.filter(is_read=False).count()
        return super().changelist_view(request, extra_context=extra_context)


class UserNotificationTypeFilter(admin.SimpleListFilter):
    title = _('Type de notification')
    parameter_name = 'user_notification_type'

    def lookups(self, request, model_admin):
        return UserNotification.Types.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())
        return queryset


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'type_badge', 'title', 'user_link', 'is_read_badge',
                    'related_application_link', 'related_evaluation_link',
                    'related_training_link', 'created_at']
    list_display_links = ['id', 'title']
    list_filter = [UserNotificationTypeFilter, 'is_read', 'created_at', 'user']
    search_fields = ['title', 'message', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'is_read_badge']
    list_per_page = 25
    actions = ['mark_as_read', 'mark_as_unread']

    fieldsets = (
        (_('📧 Notification'), {
            'fields': ('user', 'type', 'title', 'message')
        }),
        (_('🔗 Relations'), {
            'fields': ('related_application', 'related_evaluation', 'related_training'),
            'classes': ('collapse',)
        }),
        (_('📊 Statut'), {
            'fields': ('is_read', 'is_read_badge')
        }),
        (_('📅 Métadonnées'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description=_('Type'))
    def type_badge(self, obj):
        colors = {
            UserNotification.Types.EVALUATION_ASSIGNED: '#17a2b8',
            UserNotification.Types.INTERVIEW_SCHEDULED: '#ffc107',
            UserNotification.Types.APPLICATION_ACCEPTED: '#28a745',
            UserNotification.Types.TRAINING_ASSIGNED: '#6f42c1',
            UserNotification.Types.APPLICATION_REJECTED: '#dc3545',
            UserNotification.Types.APPLICATION_SHORTLISTED: '#2196F3',
            UserNotification.Types.CONTRACT_SENT: '#fd7e14',
            UserNotification.Types.CONTRACT_SIGNED: '#28a745',
        }
        color = colors.get(obj.type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 11px;">{}</span>',
            color, obj.get_type_display()
        )

    @admin.display(description=_('Utilisateur'))
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.pk])
            name = obj.user.get_full_name() or obj.user.email
            return format_html('<a href="{}" style="color: #417690;">{}</a>', url, name)
        return '-'

    @admin.display(description=_('Lu'), boolean=True)
    def is_read_badge(self, obj):
        return obj.is_read

    @admin.display(description=_('Candidature'))
    def related_application_link(self, obj):
        if obj.related_application:
            url = reverse('admin:jobs_jobapplication_change', args=[obj.related_application.pk])
            return format_html('<a href="{}">#{}</a>', url, obj.related_application.pk)
        return '-'

    @admin.display(description=_('Évaluation'))
    def related_evaluation_link(self, obj):
        if obj.related_evaluation:
            url = reverse('admin:evaluations_evaluation_change', args=[obj.related_evaluation.pk])
            return format_html('<a href="{}">{}</a>', url, obj.related_evaluation.title[:30])
        return '-'

    @admin.display(description=_('Formation'))
    def related_training_link(self, obj):
        if obj.related_training:
            url = reverse('admin:learning_course_change', args=[obj.related_training.pk])
            return format_html('<a href="{}">{}</a>', url, obj.related_training.title[:30])
        return '-'

    @admin.action(description=_('Marquer comme lues'))
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notification(s) marquée(s) comme lue(s).')

    @admin.action(description=_('Marquer comme non lues'))
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notification(s) marquée(s) comme non lue(s).')

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['total_user_notifications'] = UserNotification.objects.count()
        extra_context['unread_user_notifications'] = UserNotification.objects.filter(is_read=False).count()
        return super().changelist_view(request, extra_context=extra_context)
