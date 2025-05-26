from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.models import Technology, Profession, Domain


class TechnologyInline(admin.TabularInline):
    model = Profession.technologies.through
    extra = 1
    verbose_name = _("Technologie associée")
    verbose_name_plural = _("Technologies associées")
    autocomplete_fields = ['technology']


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'description', 'professions_count', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'professions_list']
    
    fieldsets = (
        (_('Informations générales'), {
            'fields': ('name', 'description')
        }),
        (_('Professions associées'), {
            'fields': ('professions_list',),
            'classes': ('collapse',),
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    @admin.display(description=_("Nombre de professions"))
    def professions_count(self, obj):
        return obj.professions.count()
    
    @admin.display(description=_("Professions"))
    def professions_list(self, obj):
        professions = obj.professions.all()
        if professions:
            return format_html(
                ", ".join([f'<a href="/admin/core/profession/{p.id}/change/">{p.title}</a>' for p in professions]))
        return _("Aucune profession associée")


@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'image_preview', 'professions_count', 'created_at', 'updated_at']
    list_filter = ['professions']
    search_fields = ['name']
    readonly_fields = ['image_preview', 'created_at', 'updated_at', 'professions_list']

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('name',)
        }),
        (_('Image'), {
            'fields': ('image', 'image_preview'),
            'description': _('Format recommandé: PNG ou SVG avec fond transparent, dimension 128x128px')
        }),
        (_('Professions associées'), {
            'fields': ('professions_list',),
            'classes': ('collapse',),
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_("Aperçu"))
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px;" />', obj.image.url)
        return _("Aucune image")

    @admin.display(description=_("Nombre de professions"))
    def professions_count(self, obj):
        return obj.professions.count()

    @admin.display(description=_("Professions"))
    def professions_list(self, obj):
        professions = obj.professions.all()
        if professions:
            return format_html(
                ", ".join([f'<a href="/admin/core/profession/{p.id}/change/">{p.title}</a>' for p in professions]))
        return _("Aucune profession associée")


@admin.register(Profession)
class ProfessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'domain', 'technologies_count', 'created_at', 'updated_at']
    search_fields = ['title']
    list_filter = ['domain']
    readonly_fields = ['created_at', 'updated_at', 'technologies_preview']
    filter_horizontal = ['technologies']

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('title', 'domain')
        }),
        (_('Technologies associées'), {
            'fields': ('technologies', 'technologies_preview'),
            'description': _('Sélectionnez les technologies requises pour cette profession')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_("Nombre de technologies"))
    def technologies_count(self, obj):
        return obj.technologies.count()

    @admin.display(description=_("Aperçu des technologies"))
    def technologies_preview(self, obj):
        technologies = obj.technologies.all()
        if not technologies:
            return _("Aucune technologie associée")

        tech_html = ['<div style="display: flex; flex-wrap: wrap; gap: 10px;">']
        for tech in technologies:
            if tech.image:
                tech_html.append(
                    f'<div style="text-align: center; margin: 5px;"><img src="{tech.image.url}" '
                    f'style="max-height: 40px;" /><br>{tech.name}</div>'
                )
            else:
                tech_html.append(f'<div style="text-align: center; margin: 5px;">{tech.name}</div>')
        tech_html.append('</div>')

        return format_html(''.join(tech_html))

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if form.base_fields.get('technologies'):
            form.base_fields['technologies'].help_text = _(
                'Maintenez la touche Ctrl enfoncée pour sélectionner plusieurs technologies')
        return form
