from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from candidates.models import (
    CandidateProfile, Experience, Education, Language,
    Project, ProjectImage, ProfileTechnology
)


class ProfileTechnologyInline(admin.TabularInline):
    model = ProfileTechnology
    extra = 1
    autocomplete_fields = ['technology']
    verbose_name = _("Compétence technique")
    verbose_name_plural = _("Compétences techniques")


class ExperienceInline(admin.StackedInline):
    model = Experience
    extra = 0
    fieldsets = (
        (_('Informations générales'), {
            'fields': (('title', 'company'), 'location')
        }),
        (_('Période'), {
            'fields': (('start_date', 'end_date'), 'still_working')
        }),
        (_('Description'), {
            'fields': ('description',)
        }),
    )
    verbose_name = _("Expérience professionnelle")
    verbose_name_plural = _("Expériences professionnelles")


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0
    fields = ('name', 'diploma', 'speciality', 'year_of_graduation')
    verbose_name = _("Formation")
    verbose_name_plural = _("Formations")


class LanguageInline(admin.TabularInline):
    model = Language
    extra = 0
    fields = ('name', 'level')
    verbose_name = _("Langue")
    verbose_name_plural = _("Langues")


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    readonly_fields = ['image_preview']
    fields = ('image', 'image_preview')
    verbose_name = _("Image de projet")
    verbose_name_plural = _("Images de projet")

    @admin.display(description=_("Aperçu"))
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 300px;" />', obj.image.url)
        return _("Aucune image")


class ProjectInline(admin.StackedInline):
    model = Project
    extra = 0
    fields = ('name', 'description', ('start_date', 'link'))
    verbose_name = _("Projet")
    verbose_name_plural = _("Projets")


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_fullname', 'profession', 'location', 'years_experience', 'created_at']
    list_filter = ['profession', 'disability', 'user__is_active']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'location', 'short_bio']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['user', 'profession']

    fieldsets = (
        (_('Informations utilisateur'), {
            'fields': ('user', 'profession')
        }),
        (_('Informations personnelles'), {
            'fields': ('location', 'short_bio', 'biography', 'disability')
        }),
        (_('Expérience & Formation'), {
            'fields': ('years_experience', 'other_years_experience', 'highest_degree')
        }),
        (_('Intérêts'), {
            'fields': ('interested_by',)
        }),
        (_('Métadonnées'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    inlines = [
        ProfileTechnologyInline,
        ExperienceInline,
        EducationInline,
        LanguageInline,
        ProjectInline,
    ]

    @admin.display(description=_("Nom complet"), ordering='user__first_name')
    def user_fullname(self, obj):
        return obj.user.get_full_name()


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'profile_user', 'start_date', 'created_at']
    list_filter = ['profile__profession']
    search_fields = ['name', 'description', 'profile__user__email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (_('Informations projet'), {
            'fields': ('profile', 'name', 'description')
        }),
        (_('Détails'), {
            'fields': ('start_date', 'link')
        }),
        (_('Métadonnées'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    inlines = [ProjectImageInline]

    @admin.display(description=_("Utilisateur"), ordering='profile__user__first_name')
    def profile_user(self, obj):
        return obj.profile.user.get_full_name()


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'company', 'profile_user', 'start_date', 'end_date', 'still_working']
    list_filter = ['still_working', 'profile__profession', 'company']
    search_fields = ['title', 'company', 'description', 'profile__user__email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('profile', 'title', 'company', 'location')
        }),
        (_('Période'), {
            'fields': (('start_date', 'end_date'), 'still_working')
        }),
        (_('Description'), {
            'fields': ('description',)
        }),
        (_('Métadonnées'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.display(description=_("Utilisateur"), ordering='profile__user__first_name')
    def profile_user(self, obj):
        return obj.profile.user.get_full_name()


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'diploma', 'speciality', 'year_of_graduation', 'profile_user']
    list_filter = ['year_of_graduation', 'profile__profession']
    search_fields = ['name', 'diploma', 'speciality', 'profile__user__email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('profile', 'name', 'diploma')
        }),
        (_('Détails'), {
            'fields': ('speciality', 'year_of_graduation')
        }),
        (_('Métadonnées'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.display(description=_("Utilisateur"), ordering='profile__user__first_name')
    def profile_user(self, obj):
        return obj.profile.user.get_full_name()


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'level', 'profile_user']
    list_filter = ['level', 'profile__profession']
    search_fields = ['name', 'profile__user__email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('profile', 'name', 'level')
        }),
        (_('Métadonnées'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.display(description=_("Utilisateur"), ordering='profile__user__first_name')
    def profile_user(self, obj):
        return obj.profile.user.get_full_name()


@admin.register(ProjectImage)
class ProjectImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'project_name', 'image_preview', 'created_at']
    list_filter = ['project__profile__profession']
    search_fields = ['project__name', 'project__profile__user__email']
    readonly_fields = ['image_preview', 'created_at', 'updated_at']
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('project', 'image', 'image_preview')
        }),
        (_('Métadonnées'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.display(description=_("Projet"), ordering='project__name')
    def project_name(self, obj):
        return obj.project.name

    @admin.display(description=_("Aperçu"))
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 300px;" />', obj.image.url)
        return _("Aucune image")
