from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'website', 'city', 'country', 'created_at')
    list_filter = ('country', 'city', 'created_at')
    search_fields = ('name', 'account__email', 'city', 'country')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('name', 'description', 'account')
        }),
        (_('Localisation'), {
            'fields': ('address', 'city', 'country')
        }),
        (_('Médias'), {
            'fields': ('logo', 'website')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
