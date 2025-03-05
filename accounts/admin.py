from django.contrib import admin

from accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'full_name', 'experience_display', 'get_domain_name', 'is_active', 'is_staff',
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
        ('Personal Info', {
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

    @admin.display(description='Full Name')
    def full_name(self, obj):
        return obj.get_full_name()

    @admin.display(description='Experience')
    def experience_display(self, obj):
        return obj.get_experience_level_display()

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

    def get_domain_name(self, obj):
        return obj.domain.name if obj.domain else ""

    get_domain_name.admin_order_field = 'domain__name'  # Permet le tri sur ce champ
    get_domain_name.short_description = 'Domain Name'
