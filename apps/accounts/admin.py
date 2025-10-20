from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User

admin.site.site_header = 'WIB Challenge Administration'
admin.site.site_title  = 'WIB Admin'
admin.site.index_title = 'Panneau d\'administration'


class RoleFilter(admin.SimpleListFilter):
    title = _('Rôle utilisateur')
    parameter_name = 'role'

    def lookups(self, request, model_admin):
        return User.Roles.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(role=self.value())
        return queryset


class RecentlyJoinedFilter(admin.SimpleListFilter):
    title = _('Inscription récente')
    parameter_name = 'recent'

    def lookups(self, request, model_admin):
        return ('7', _('Cette semaine')), ('30', _('Ce mois')), ('90', _('Ces 3 mois')),

    def queryset(self, request, queryset):
        if self.value():
            days = int(self.value())
            cutoff_date = timezone.now() - timedelta(days=days)
            return queryset.filter(date_joined__gte=cutoff_date)
        return queryset


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name_display', 'role_badge', 'phone', 'is_active_display', 'date_joined_display',
                    'picture_preview')
    list_display_links = ('email', 'full_name_display')
    list_filter = (RoleFilter, 'is_active', 'is_staff', 'is_superuser', RecentlyJoinedFilter, 'date_joined',
                   'updated_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    readonly_fields = ('username', 'date_joined', 'last_login', 'updated_at', 'picture_preview_large', 'user_stats')

    list_select_related = ()
    list_per_page = 25
    actions = ['activate_users', 'deactivate_users', 'promote_to_evaluator', 'reset_to_developer']

    fieldsets = ((None, {'fields': ('email', 'password')}),
                 (_('Informations personnelles'), {'fields': ('first_name', 'last_name', 'phone')}),
                 (_('Photo de profil'), {'fields': ('picture', 'picture_preview_large'), 'classes': ('collapse',)}),
                 (_('Autorisations'),
                  {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
                   'classes': ('collapse',)}), (_('Dates importantes'),
                                                {'fields': ('last_login', 'date_joined', 'updated_at'),
                                                 'classes': ('collapse',)}),
                 (_('Métadonnées'), {'fields': ('username', 'user_stats'), 'classes': ('collapse',)}),)

    add_fieldsets = ((None, {'classes': ('wide',),
                             'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'role'), }),)

    def get_queryset(self, request):
        return super().get_queryset(request)

    @admin.display(description=_('Nom complet'))
    def full_name_display(self, obj):
        """Affiche le nom complet avec les initiales"""
        return f"{obj.full_name}" if obj.full_name.strip() else f"({obj.initials})"

    @admin.display(description=_('Rôle'))
    def role_badge(self, obj):
        """Affiche le rôle avec une couleur"""
        colors = {
            User.Roles.ADMIN: '#dc3545',
            User.Roles.USER: '#28a745',
            User.Roles.ORGANIZATION: '#007bff',
            User.Roles.EVALUATOR: '#fd7e14'
        }
        color = colors.get(obj.role, '#ccc')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_role_display())

    @admin.display(description=_('Statut'), boolean=True)
    def is_active_display(self, obj):
        """Affiche le statut actif avec une icône"""
        return obj.is_active

    @admin.display(description=_('Inscription'))
    def date_joined_display(self, obj):
        """Affiche la date d'inscription formatée"""
        if obj.is_recently_joined():
            return format_html('<span style="color: blue; font-weight: bold;">{}</span>',
                               obj.date_joined.strftime('%d/%m/%Y'))
        return obj.date_joined.strftime('%d/%m/%Y')

    @admin.display(description=_('Photo'))
    def picture_preview(self, obj):
        """Miniature de la photo de profil"""
        if obj.picture:
            return format_html(
                '<img src="{}" style="width: 30px; height: 30px; border-radius: 50%; object-fit: cover;" />',
                obj.picture.url)
        return format_html(
            '<div style="width: 30px; height: 30px; background: #ddd; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px;">{}</div>',
            obj.initials)

    @admin.display(description=_('Aperçu de la photo'))
    def picture_preview_large(self, obj):
        """Grande prévisualisation de la photo"""
        if obj.picture:
            return format_html('<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px;" />',
                               obj.picture.url)
        return _('Aucune photo')

    @admin.display(description=_('Statistiques'))
    def user_stats(self, obj):
        """Statistiques de l'utilisateur"""
        stats = []
        if obj.is_recently_joined():
            stats.append('<span style="color: green;">• Nouvel utilisateur</span>')
        if obj.is_superuser:
            stats.append('<span style="color: red;">• Super utilisateur</span>')
        if obj.is_staff:
            stats.append('<span style="color: orange;">• Staff</span>')
        if obj.is_admin:
            stats.append('<span style="color: purple;">• Administrateur</span>')
        if obj.is_evaluator:
            stats.append('<span style="color: orange;">• Évaluateur</span>')

        return format_html('<br>'.join(stats)) if stats else _('Utilisateur standard')

    # Actions personnalisées
    @admin.action(description=_('Activer les utilisateurs sélectionnés'))
    def activate_users(self, request, queryset):
        """Active les utilisateurs sélectionnés"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} utilisateur(s) activé(s).')

    @admin.action(description=_('Désactiver les utilisateurs sélectionnés'))
    def deactivate_users(self, request, queryset):
        """Désactive les utilisateurs sélectionnés"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} utilisateur(s) désactivé(s).')

    def get_readonly_fields(self, request, obj=None):
        """Champs en lecture seule selon les permissions"""
        readonly = list(self.readonly_fields)
        if obj and not request.user.is_superuser:
            if obj.is_superuser or (obj.is_admin and not request.user.is_admin):
                readonly.extend(['role', 'is_active', 'is_staff', 'is_superuser'])
        return readonly

    def has_delete_permission(self, request, obj=None):
        """Permission de suppression"""
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def changelist_view(self, request, extra_context=None):
        """Ajoute des statistiques à la vue liste"""
        extra_context = extra_context or {}

        # Statistiques globales
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        recent_users = User.objects.recent_users().count()

        role_stats = User.objects.values('role').annotate(count=Count('id'))

        extra_context.update({'total_users': total_users, 'active_users': active_users, 'recent_users': recent_users,
                              'role_stats': role_stats, })

        return super().changelist_view(request, extra_context=extra_context)
