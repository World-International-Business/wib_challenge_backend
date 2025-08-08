from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.candidates.models import (
    CandidateProfile, Experience, Education, Language,
    Project, ProjectImage, ProfileTechnology
)


class DisabilityFilter(admin.SimpleListFilter):
    title = _('Statut handicap')
    parameter_name = 'disability_status'

    def lookups(self, request, model_admin):
        return (
            ('yes', _('En situation de handicap')),
            ('no', _('Sans handicap déclaré')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(disability=True)
        if self.value() == 'no':
            return queryset.filter(disability=False)
        return queryset


class ExperienceRangeFilter(admin.SimpleListFilter):
    title = _('Niveau d\'expérience')
    parameter_name = 'experience_range'

    def lookups(self, request, model_admin):
        return (
            ('junior', _('Junior (0-2 ans)')),
            ('mid', _('Confirmé (3-5 ans)')),
            ('senior', _('Senior (6+ ans)')),
            ('expert', _('Expert (10+ ans)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'junior':
            return queryset.filter(years_experience__lte=2)
        elif self.value() == 'mid':
            return queryset.filter(years_experience__gte=3, years_experience__lte=5)
        elif self.value() == 'senior':
            return queryset.filter(years_experience__gte=6, years_experience__lte=9)
        elif self.value() == 'expert':
            return queryset.filter(years_experience__gte=10)
        return queryset


class ProfileTechnologyInline(admin.TabularInline):
    model = ProfileTechnology
    extra = 1
    autocomplete_fields = ['technology']
    verbose_name = _("Compétence technique")
    verbose_name_plural = _("Compétences techniques")
    fields = ['technology', 'level', 'level_badge']
    readonly_fields = ['level_badge']

    @admin.display(description=_("Niveau visuel"))
    def level_badge(self, obj):
        if obj.level is None:
            return _("Non défini")

        if obj.level >= 80:
            color, label = '#28a745', 'Expert'
        elif obj.level >= 60:
            color, label = '#007bff', 'Avancé'
        elif obj.level >= 40:
            color, label = '#ffc107', 'Intermédiaire'
        else:
            color, label = '#dc3545', 'Débutant'

        return format_html(
            '<div style="background: {}; width: {}%; height: 20px; border-radius: 3px; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px;">{}</div>',
            color, obj.level, label
        )


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
    fields = ('name', 'level', 'level_display')
    readonly_fields = ['level_display']
    verbose_name = _("Langue")
    verbose_name_plural = _("Langues")

    @admin.display(description=_("Niveau %"))
    def level_display(self, obj):
        if obj.level is None:
            return _("Non défini")
        return f"{obj.level}%"


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
    list_display = [
        'id', 'user_fullname', 'profession_display', 'location', 'experience_badge',
        'degree_display', 'disability_status', 'work_status', 'tech_count', 'created_at'
    ]
    list_display_links = ['id', 'user_fullname']
    list_filter = [
        'profession', DisabilityFilter, 'open_to_work', ExperienceRangeFilter,
        'user__is_active', 'created_at'
    ]
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'location', 'short_bio', 'biography', 'interested_by'
    ]
    readonly_fields = ['created_at', 'updated_at', 'profile_stats']
    autocomplete_fields = ['user', 'profession']
    list_per_page = 25
    actions = ['mark_open_to_work', 'mark_not_open_to_work', 'export_profiles']

    fieldsets = (
        (_('Informations utilisateur'), {
            'fields': ('user', 'profession')
        }),
        (_('Informations personnelles'), {
            'fields': ('location', 'short_bio', 'biography', 'disability')
        }),
        (_('Statut professionnel'), {
            'fields': ('open_to_work', 'interested_by')
        }),
        (_('Expérience & Formation'), {
            'fields': (('years_experience', 'other_years_experience'), 'highest_degree')
        }),
        (_('Statistiques'), {
            'fields': ('profile_stats',),
            'classes': ('collapse',)
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'profession').prefetch_related(
            'technologies', 'experiences', 'educations', 'languages', 'projects'
        )

    @admin.display(description=_("Nom complet"), ordering='user__first_name')
    def user_fullname(self, obj):
        full_name = obj.user.get_full_name()
        if obj.user.is_active:
            return full_name
        return format_html('<span style="color: #999; text-decoration: line-through;">{}</span>', full_name)

    @admin.display(description=_("Profession"))
    def profession_display(self, obj):
        if obj.profession:
            return format_html('<span style="background: #e9ecef; padding: 2px 6px; border-radius: 3px;">{}</span>',
                               obj.profession.title)
        return _("Non spécifiée")

    @admin.display(description=_("Expérience"))
    def experience_badge(self, obj):
        if obj.years_experience is None:
            return format_html('<span style="color: #999;">Non renseigné</span>')

        if obj.years_experience <= 2:
            color, label = '#17a2b8', 'Junior'
        elif obj.years_experience <= 5:
            color, label = '#28a745', 'Confirmé'
        elif obj.years_experience <= 9:
            color, label = '#fd7e14', 'Senior'
        else:
            color, label = '#6f42c1', 'Expert'

        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{} ({} ans)</span>',
            color, label, obj.years_experience
        )

    @admin.display(description=_("Diplôme"))
    def degree_display(self, obj):
        if obj.highest_degree is None:
            return _("Non renseigné")
        return f"Bac +{obj.highest_degree}"

    @admin.display(description=_("Handicap"), boolean=True)
    def disability_status(self, obj):
        return obj.disability

    @admin.display(description=_("Recherche emploi"), boolean=True)
    def work_status(self, obj):
        return obj.open_to_work

    @admin.display(description=_("Technologies"))
    def tech_count(self, obj):
        count = obj.technologies.count()
        if count == 0:
            return format_html('<span style="color: #999;">0</span>')
        return format_html('<strong>{}</strong>', count)

    @admin.display(description=_("Statistiques du profil"))
    def profile_stats(self, obj):
        stats = []

        exp_count = obj.experiences.count()
        edu_count = obj.educations.count()
        proj_count = obj.projects.count()
        lang_count = obj.languages.count()
        tech_count = obj.technologies.count()

        stats.append(f'<strong>Complétude du profil:</strong>')
        stats.append(f'• {exp_count} expérience(s)')
        stats.append(f'• {edu_count} formation(s)')
        stats.append(f'• {proj_count} projet(s)')
        stats.append(f'• {lang_count} langue(s)')
        stats.append(f'• {tech_count} technologie(s)')

        score = 0
        score += 10 if obj.short_bio else 0
        score += 15 if obj.biography else 0
        score += 15 if exp_count > 0 else 0
        score += 10 if edu_count > 0 else 0
        score += 10 if proj_count > 0 else 0
        score += 15 if tech_count > 0 else 0
        score += 10 if lang_count > 0 else 0
        score += 15 if obj.years_experience is not None else 0

        color = '#28a745' if score >= 70 else '#ffc107' if score >= 50 else '#dc3545'
        stats.append(f'<br><strong style="color: {color};">Score: {score}%</strong>')

        return format_html('<br>'.join(stats))

    @admin.action(description=_("Marquer comme 'recherche emploi'"))
    def mark_open_to_work(self, request, queryset):
        updated = queryset.update(open_to_work=True)
        self.message_user(request, f'{updated} profil(s) marqué(s) en recherche d\'emploi.')

    @admin.action(description=_("Marquer comme 'ne recherche pas'"))
    def mark_not_open_to_work(self, request, queryset):
        updated = queryset.update(open_to_work=False)
        self.message_user(request, f'{updated} profil(s) marqué(s) comme ne recherchant pas d\'emploi.')

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        total_profiles = CandidateProfile.objects.count()
        open_to_work = CandidateProfile.objects.filter(open_to_work=True).count()
        with_disability = CandidateProfile.objects.filter(disability=True).count()
        recent_profiles = CandidateProfile.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()

        extra_context.update({
            'total_profiles': total_profiles,
            'open_to_work': open_to_work,
            'with_disability': with_disability,
            'recent_profiles': recent_profiles,
        })

        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'profile_user', 'start_date', 'has_link', 'images_count', 'created_at']
    list_display_links = ['id', 'name']
    list_filter = ['profile__profession', 'start_date']
    search_fields = ['name', 'description', 'profile__user__email', 'profile__user__first_name']
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile__user').prefetch_related('images')

    @admin.display(description=_("Utilisateur"), ordering='profile__user__first_name')
    def profile_user(self, obj):
        return obj.profile.user.get_full_name()

    @admin.display(description=_("Lien"), boolean=True)
    def has_link(self, obj):
        return bool(obj.link)

    @admin.display(description=_("Images"))
    def images_count(self, obj):
        count = obj.images.count()
        if count == 0:
            return format_html('<span style="color: #999;">0</span>')
        return format_html('<strong>{}</strong>', count)


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'company', 'profile_user', 'duration_display',
        'location', 'still_working', 'created_at'
    ]
    list_display_links = ['id', 'title']
    list_filter = ['still_working', 'profile__profession', 'company', 'start_date']
    search_fields = ['title', 'company', 'description', 'location', 'profile__user__email']
    readonly_fields = ['created_at', 'updated_at', 'duration_display']
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile__user')

    @admin.display(description=_("Utilisateur"), ordering='profile__user__first_name')
    def profile_user(self, obj):
        return obj.profile.user.get_full_name()

    @admin.display(description=_("Durée"))
    def duration_display(self, obj):
        if obj.still_working:
            return format_html('<span style="color: green;">En cours</span>')
        elif obj.end_date:
            duration = obj.end_date - obj.start_date
            years = duration.days // 365
            months = (duration.days % 365) // 30
            if years > 0:
                return f"{years} an(s) {months} mois"
            else:
                return f"{months} mois"
        return _("Durée inconnue")
