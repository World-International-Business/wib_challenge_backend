from django.contrib import admin

from accounts.models import User, UserSkill

admin.site.site_header = 'WIB Challenge Administration'

class UserSkillInline(admin.TabularInline):  # Affichage en tableau (peut aussi être `StackedInline`)
    model = UserSkill
    extra = 1

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'full_name', 'experience_display', 'get_domain_name', 'display_skills', 'is_active', 'is_staff',
                    'date_joined']
    list_filter = ['is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    list_display_links = ['email']
    ordering = ['id']
    readonly_fields = ['id', 'date_joined', 'last_login', 'is_superuser']
    fieldsets = (
        (None, {
            'fields': ('email',)
        }),
        ('Informations Personnelles', {
            'fields': ('first_name', 'last_name', 'domain', 'experience_level', 'experience')
        }),
        ('Challenges', {
            'fields': ('challenges',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser')
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    inlines = [UserSkillInline]

    @admin.display(description='Full Name')
    def full_name(self, obj):
        return obj.get_full_name()

    @admin.display(description='Experience')
    def experience_display(self, obj):
        return obj.get_experience_level_display()

    def display_skills(self, obj):
        return ", ".join([skill.skill.name for skill in obj.userskill_set.all()]) if obj.userskill_set.exists() else "-"

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
        # if obj.challenges.filter(domain=form.instance.domain).count() != obj.challenges.count():
        #     raise ValidationError('Les challenges sélectionnés ne sont pas du même domaine que l\'utilisateur')

    @admin.display(ordering='domain__name', description='Domain', empty_value='-')
    def get_domain_name(self, obj):
        return obj.domain.name if obj.domain else None
