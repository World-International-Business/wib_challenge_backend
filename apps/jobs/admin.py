from django.contrib import admin, messages
from django.db import models
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import JobCategory, JobOffer


@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'job_offers_count', 'published_jobs_count']
    search_fields = ['title', 'description']
    # prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['job_offers_count', 'published_jobs_count']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            total_jobs=Count('job_offers'),
            published_jobs=Count('job_offers', filter=models.Q(job_offers__status='published'))
        )

    @admin.display(description=_('Total des offres'), ordering='total_jobs')
    def job_offers_count(self, obj):
        count = getattr(obj, 'total_jobs', 0)
        if count > 0:
            url = reverse('admin:jobs_joboffer_changelist') + f'?category__id__exact={obj.id}'
            return format_html(
                '<a href="{}" class="button" style="background-color: #417690; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">{}</a>',
                url, count
            )
        return count

    @admin.display(description=_('Offres publiées'), ordering='published_jobs')
    def published_jobs_count(self, obj):
        count = getattr(obj, 'published_jobs', 0)
        if count > 0:
            url = reverse('admin:jobs_joboffer_changelist') + f'?category__id__exact={obj.id}&status__exact=published'
            return format_html(
                '<a href="{}" class="button" style="background-color: #28a745; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">{}</a>',
                url, count
            )
        return count


class JobOfferStatusFilter(admin.SimpleListFilter):
    title = _('Statut détaillé')
    parameter_name = 'status_detail'

    def lookups(self, request, model_admin):
        return [
            ('active', _('Actives (publiées non expirées)')),
            ('expired', _('Expirées')),
            ('draft', _('Brouillons')),
            ('filled', _('Fermées')),
            ('featured', _('Mises en avant')),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(
                status='published',
                expires_at__gt=timezone.now()
            )
        elif self.value() == 'expired':
            return queryset.filter(
                status='published',
                expires_at__lte=timezone.now()
            )
        elif self.value() == 'featured':
            return queryset.filter(featured=True)
        elif self.value() in ['draft', 'filled']:
            return queryset.filter(status=self.value())
        return queryset


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'company_link', 'category_link', 'status_badge',
        'featured_badge', 'salary_display', 'location', 'job_type',
        'published_date', 'expires_date', 'applications_count'
    ]
    list_filter = [
        JobOfferStatusFilter, 'featured', 'job_type', 'experience_level',
        'remote_allowed', 'category', 'company', 'created_at', 'published_at'
    ]
    search_fields = [
        'title', 'description', 'company__name', 'location', 'requirements'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'published_at',
        'company_info', 'category_info', 'view_on_site_link'
    ]
    # prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    list_per_page = 20

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['title', 'company', 'category', 'status', 'featured']
        }),
        (_('Détails du poste'), {
            'fields': ['description', 'responsibilities', 'requirements', 'benefits']
        }),
        (_('Conditions'), {
            'fields': [
                'job_type', 'experience_level', 'location', 'remote_allowed',
                ('salary_min', 'salary_max', 'currency')
            ]
        }),
        (_('Candidature'), {
            'fields': ['application_url', 'application_email']
        }),
        (_('Dates'), {
            'fields': ['expires_at', 'published_at', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
        (_('Informations complémentaires'), {
            'fields': ['company_info', 'category_info', 'view_on_site_link'],
            'classes': ['collapse']
        })
    ]

    actions = [
        'make_featured', 'remove_featured', 'publish_offers',
        'unpublish_offers', 'mark_as_filled', 'extend_expiry'
    ]

    @admin.display(description=_('Entreprise'), ordering='company__name')
    def company_link(self, obj):
        if obj.company:
            url = reverse('admin:organizations_organization_change', args=[obj.company.pk])
            return format_html(
                '<a href="{}" style="color: #417690; font-weight: bold;">{}</a>',
                url, obj.company.name
            )
        return '-'

    @admin.display(description=_('Catégorie'), ordering='category__title')
    def category_link(self, obj):
        if obj.category:
            url = reverse('admin:jobs_jobcategory_change', args=[obj.category.pk])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.category.title
            )
        return '-'

    @admin.display(description=_('Statut'), ordering='status')
    def status_badge(self, obj):
        colors = {
            'draft': '#6c757d',
            'published': '#28a745',
            'expired': '#dc3545',
            'filled': '#17a2b8'
        }
        labels = {
            'draft': 'Brouillon',
            'published': 'Publié',
            'expired': 'Expiré',
            'filled': 'Fermé'
        }

        color = colors.get(obj.status, '#6c757d')
        label = labels.get(obj.status, obj.status)

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, label
        )

    @admin.display(description=_('Mise en avant'))
    def featured_badge(self, obj):
        return format_html(
            '<span style="color: #ffc107; font-size: 16px;">{}</span>',
            '⭐' if obj.featured else '-'
        )

    @admin.display(description=_('Salaire'), ordering='salary_min')
    def salary_display(self, obj):
        if obj.salary_min and obj.salary_max:
            return f"{obj.salary_min:,.0f} - {obj.salary_max:,.0f} {obj.currency}"
        elif obj.salary_min:
            return f"À partir de {obj.salary_min:,.0f} {obj.currency}"
        elif obj.salary_max:
            return f"Jusqu'à {obj.salary_max:,.0f} {obj.currency}"
        return "Non spécifié"

    @admin.display(description=_('Publié le'), ordering='published_at')
    def published_date(self, obj):
        if obj.published_at:
            return obj.published_at.strftime('%d/%m/%Y')
        return '-'

    @admin.display(description=_('Expire le'), ordering='expires_at')
    def expires_date(self, obj):
        if obj.expires_at:
            now = timezone.now()
            if obj.expires_at < now:
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;">{}</span>',
                    obj.expires_at.strftime('%d/%m/%Y')
                )
            return obj.expires_at.strftime('%d/%m/%Y')
        return '-'

    @admin.display(description=_('Candidatures'))
    def applications_count(self, obj):
        # Placeholder - à adapter selon votre modèle d'application
        return format_html(
            '<span style="background-color: #e9ecef; padding: 2px 6px; border-radius: 8px; font-size: 11px;">0</span>'
        )

    @admin.display(description=_('Informations entreprise'))
    def company_info(self, obj):
        if obj.company:
            return format_html(
                '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
                '<strong>{}</strong><br>'
                '<small>{}, {}</small><br>'
                '<a href="{}" target="_blank" style="color: #417690;">Voir le profil</a>'
                '</div>',
                obj.company.name,
                obj.company.city or 'Ville non spécifiée',
                obj.company.country or 'Pays non spécifié',
                reverse('admin:organizations_organization_change', args=[obj.company.pk])
            )
        return '-'

    @admin.display(description=_('Informations catégorie'))
    def category_info(self, obj):
        if obj.category:
            return format_html(
                '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
                '<strong>{}</strong><br>'
                '<small>{}</small>'
                '</div>',
                obj.category.title,
                obj.category.description or 'Pas de description'
            )
        return '-'

    @admin.display(description=_('Voir sur le site'))
    def view_on_site_link(self, obj):
        if obj.slug:
            # Adapter l'URL selon votre configuration
            url = f"/jobs/{obj.slug}/"
            return format_html(
                '<a href="{}" target="_blank" class="button" style="background-color: #417690; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">Voir l\'offre</a>',
                url
            )
        return '-'

    @admin.action(description=_('Mettre en avant les offres sélectionnées'))
    def make_featured(self, request, queryset):
        updated = queryset.update(featured=True)
        self.message_user(
            request,
            f"{updated} offre(s) mise(s) en avant avec succès.",
            messages.SUCCESS
        )

    @admin.action(description=_('Retirer la mise en avant'))
    def remove_featured(self, request, queryset):
        updated = queryset.update(featured=False)
        self.message_user(
            request,
            f"{updated} offre(s) retirée(s) de la mise en avant.",
            messages.SUCCESS
        )

    @admin.action(description=_('Publier les offres sélectionnées'))
    def publish_offers(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status='draft').update(
            status='published',
            published_at=now
        )
        self.message_user(
            request,
            f"{updated} offre(s) publiée(s) avec succès.",
            messages.SUCCESS
        )

    @admin.action(description=_('Dépublier les offres sélectionnées'))
    def unpublish_offers(self, request, queryset):
        updated = queryset.filter(status='published').update(status='draft')
        self.message_user(
            request,
            f"{updated} offre(s) dépubliée(s) avec succès.",
            messages.SUCCESS
        )

    @admin.action(description=_('Marquer comme fermées'))
    def mark_as_filled(self, request, queryset):
        updated = queryset.update(status='filled')
        self.message_user(
            request,
            f"{updated} offre(s) marquée(s) comme fermée(s).",
            messages.SUCCESS
        )

    @admin.action(description=_('Prolonger l\'expiration de 30 jours'))
    def extend_expiry(self, request, queryset):
        from datetime import timedelta
        updated = 0
        for obj in queryset:
            if obj.expires_at:
                obj.expires_at += timedelta(days=30)
                obj.save()
                updated += 1
        self.message_user(
            request,
            f"{updated} offre(s) prolongée(s) de 30 jours.",
            messages.SUCCESS
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('company', 'category')
