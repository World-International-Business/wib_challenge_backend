from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'sector', 'company_size', 'city', 'country', 'created_at')
    list_filter = ('country', 'city', 'company_size', 'created_at')
    search_fields = ('name', 'account__email', 'sector', 'city', 'country', 'neighborhood')
    readonly_fields = ('created_at', 'updated_at')
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
            'fields': ('logo',)
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
