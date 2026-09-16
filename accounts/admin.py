from django.contrib import admin
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.html import format_html

from accounts.models import User, UserSkill
from wib_challenge.enums import ExperienceLevel

admin.site.site_header = 'WIB Challenge Administration'


class UserSkillInline(admin.TabularInline):
    model = UserSkill
    extra = 1
    autocomplete_fields = ['skill']
    verbose_name = "Compétence"
    verbose_name_plural = "Compétences"

    fieldsets = (
        (None, {
            'fields': ('skill', 'experience_level')
        }),
    )


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ['user', 'skill', 'experience_level_display']
    list_filter = ['experience_level', 'skill']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'skill__name']
    autocomplete_fields = ['user', 'skill']

    fieldsets = (
        (None, {
            'fields': ('user', 'skill', 'experience_level')
        }),
    )

    @admin.display(description='Niveau d\'expérience', ordering='experience_level')
    def experience_level_display(self, obj):
        colors = {
            ExperienceLevel.BEGINNER: 'blue',
            ExperienceLevel.INTERMEDIATE: 'green',
            ExperienceLevel.EXPERT: 'red',
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.experience_level, 'black'),
            obj.get_experience_level_display()
        )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'full_name', 'experience_display', 'get_domain_name', 'display_skills',
                    'challenges_count', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'experience_level', 'domain', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'skills__name']
    list_display_links = ['email']
    ordering = ['-date_joined']
    readonly_fields = ['id', 'date_joined', 'last_login', 'is_superuser']
    filter_horizontal = ['challenges']
    autocomplete_fields = ['domain']

    fieldsets = (
        (None, {
            'fields': ('email',)
        }),
        ('Informations Personnelles', {
            'fields': ('first_name', 'last_name', 'domain', 'experience_level', 'experience'),
            'classes': ('wide',),
        }),
        ('Challenges', {
            'fields': ('challenges',),
            'classes': ('collapse',),
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Dates importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    inlines = [UserSkillInline]
    actions = ['send_candidate_invitations']

    @admin.action(description='Envoyer une invitation aux candidats sélectionnés')
    def send_candidate_invitations(self, request, queryset):
        sent = 0
        for user in queryset.filter(is_staff=False, is_superuser=False, is_active=True):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_path = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            reset_url = request.build_absolute_uri(reset_path)
            site_url = request.build_absolute_uri(reverse('home'))
            send_mail(
                'Invitation à WIB Challenge',
                (
                    f'Bonjour {user.first_name},\n\n'
                    f'Vous êtes invité(e) à passer votre évaluation : {site_url}\n\n'
                    f'Créez ou définissez votre mot de passe ici : {reset_url}\n'
                ),
                None,
                [user.email],
                fail_silently=False,
            )
            sent += 1
        self.message_user(request, f'{sent} invitation(s) envoyée(s).')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('skills_infos__skill', 'domain', 'challenges')

    @admin.display(description='Nom complet', ordering='first_name')
    def full_name(self, obj):
        return obj.get_full_name()

    @admin.display(description='Expérience', ordering='experience_level')
    def experience_display(self, obj):
        colors = {
            ExperienceLevel.BEGINNER: 'blue',
            ExperienceLevel.INTERMEDIATE: 'green',
            ExperienceLevel.EXPERT: 'red',
        }
        return format_html(
            '<span style="color: {};">{} ({} années)</span>',
            colors.get(obj.experience_level, 'black'),
            obj.get_experience_level_display(),
            obj.experience
        )

    @admin.display(description='Compétences')
    def display_skills(self, obj):
        skills = obj.skills_infos.all()
        if not skills:
            return "-"

        skills_html = []
        for skill_info in skills:
            skill_level = skill_info.get_experience_level_display()
            skills_html.append(f"{skill_info.skill.name} ({skill_level})")

        return format_html(", ".join(skills_html))

    @admin.display(description='Challenges', ordering='challenges__count')
    def challenges_count(self, obj):
        count = obj.challenges.count()
        return count if count > 0 else "-"

    def delete_queryset(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, 'Les utilisateurs sélectionnés ont été désactivés avec succès.')

    def get_fieldsets(self, request, obj=None):
        if not obj:
            fieldsets = list(self.fieldsets)
            fieldsets[0] = (None, {'fields': ('email', 'password')})
            return fieldsets
        return super().get_fieldsets(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.set_password(obj.password)
        super().save_model(request, obj, form, change)

    @admin.display(ordering='domain__name', description='Domaine', empty_value='-')
    def get_domain_name(self, obj):
        return obj.domain.name if obj.domain else None
