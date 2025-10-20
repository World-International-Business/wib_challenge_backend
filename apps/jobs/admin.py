from django.contrib import admin, messages
from django.db import models
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import JobCategory, JobOffer, JobApplication


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
            url = reverse('admin:jobs_joboffer_changelist') + f'?poste__id__exact={obj.id}'
            return format_html(
                '<a href="{}" class="button" style="background-color: #417690; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">{}</a>',
                url, count
            )
        return count

    @admin.display(description=_('Offres publiées'), ordering='published_jobs')
    def published_jobs_count(self, obj):
        count = getattr(obj, 'published_jobs', 0)
        if count > 0:
            url = reverse('admin:jobs_joboffer_changelist') + f'?poste__id__exact={obj.id}&status__exact=published'
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
        'title', 'company_link', 'poste_link', 'status_badge',
        'featured_badge', 'salary_display', 'location', 'job_type',
        'published_date', 'expires_date', 'applications_count'
    ]
    list_filter = [
        JobOfferStatusFilter, 'featured', 'job_type', 'experience_level',
        'remote_allowed', 'poste', 'company', 'created_at', 'published_at'
    ]
    search_fields = [
        'title', 'description', 'company__name', 'location', 'requirements'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'published_at',
        'company_info', 'poste_info', 'view_on_site_link'
    ]
    # prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    list_per_page = 20

    fieldsets = [
        (_('Informations générales'), {
            'fields': ['title', 'company', 'poste', 'status', 'featured']
        }),
        (_('Détails du poste'), {
            'fields': ['description', 'responsibilities', 'requirements', 'benefits','skills']
        }),
        (_('Conditions'), {
            'fields': [
                'job_type', 'experience_level', 'location', 'remote_allowed',
                ('salary', 'currency')
            ]
        }),
        (_('Candidature'), {
            'fields': ['application_url', 'application_email', 'attachments', 'required_documents']
        }),
        (_('Dates'), {
            'fields': ['expires_at', 'published_at', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
        (_('Informations complémentaires'), {
            'fields': ['company_info', 'poste_info', 'view_on_site_link'],
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

    @admin.display(description=_('Poste'), ordering='poste__title')
    def poste_link(self, obj):
        if obj.poste:
            url = reverse('admin:jobs_jobcategory_change', args=[obj.poste.pk])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.poste.title
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

    @admin.display(description=_('Salaire'), ordering='salary')
    def salary_display(self, obj):
        if obj.salary:
            return f"{obj.salary} {obj.currency}"
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

    @admin.display(description=_('Candidatures'), ordering='total_applications')
    def applications_count(self, obj):
        count = getattr(obj, 'total_applications', 0)
        if count > 0:
            return format_html(
                '<a href="{}" style="background-color: #28a745; color: white; padding: 2px 8px; border-radius: 8px; font-size: 11px; text-decoration: none; font-weight: bold;">{}</a>',
                reverse('admin:jobs_jobapplication_changelist') + f'?job_offer__id__exact={obj.id}',
                count
            )
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

    @admin.display(description=_('Informations poste'))
    def poste_info(self, obj):
        if obj.poste:
            return format_html(
                '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
                '<strong>{}</strong><br>'
                '<small>{}</small>'
                '</div>',
                obj.poste.title,
                obj.poste.description or 'Pas de description'
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
        return queryset.select_related('company', 'poste').annotate(
            total_applications=Count('applications')
        )


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ['applicant_name', 'applicant_email', 'job_offer_link', 'status_badge', 'ai_decision_badge', 'submitted_at']
    list_filter = ['status', 'submitted_at', 'ai_decision', 'job_offer__company']
    search_fields = ['applicant_name', 'applicant_email', 'job_offer__title', 'user__email']
    readonly_fields = ['submitted_at', 'ai_analysis', 'ai_decision']
    actions = ['mark_as_shortlisted', 'mark_as_accepted', 'mark_as_rejected', 'mark_as_pending']
    date_hierarchy = 'submitted_at'
    list_per_page = 20

    fieldsets = [
        (_('Informations candidat'), {
            'fields': ['applicant_name', 'applicant_email', 'user']
        }),
        (_('Offre d\'emploi'), {
            'fields': ['job_offer', 'status']
        }),
        (_('Documents'), {
            'fields': ['resume', 'cover_letter']
        }),
        (_('Analyse IA'), {
            'fields': ['ai_analysis', 'ai_decision'],
            'classes': ['collapse']
        }),
        (_('Dates'), {
            'fields': ['submitted_at'],
            'classes': ['collapse']
        })
    ]

    @admin.display(description=_('Offre d\'emploi'), ordering='job_offer__title')
    def job_offer_link(self, obj):
        if obj.job_offer:
            url = reverse('admin:jobs_joboffer_change', args=[obj.job_offer.pk])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.job_offer.title
            )
        return '-'

    @admin.display(description=_('Statut'), ordering='status')
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',      # Orange
            'shortlisted': '#2196F3',  # Bleu
            'accepted': '#4caf50',     # Vert
            'rejected': '#f44336'      # Rouge
        }
        labels = {
            'pending': 'En attente',
            'shortlisted': 'Présélectionné',
            'accepted': 'Retenu',
            'rejected': 'Rejeté'
        }
        color = colors.get(obj.status, '#9e9e9e')
        label = labels.get(obj.status, obj.status)
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold; '
            'display: inline-block;">{}</span>',
            color, label
        )

    @admin.display(description=_('Décision IA'), ordering='ai_decision')
    def ai_decision_badge(self, obj):
        if obj.ai_decision is None:
            return format_html(
                '<span style="color: #9e9e9e;">-</span>'
            )
        elif obj.ai_decision:
            return format_html(
                '<span style="color: #4caf50; font-weight: bold;">✓ Recommandé</span>'
            )
        else:
            return format_html(
                '<span style="color: #f44336; font-weight: bold;">✗ Non recommandé</span>'
            )

    @admin.action(description=_('Marquer comme présélectionné'))
    def mark_as_shortlisted(self, request, queryset):
        updated = queryset.update(status='shortlisted')
        self.message_user(
            request,
            f"{updated} candidature(s) marquée(s) comme présélectionnée(s).",
            messages.SUCCESS
        )

    @admin.action(description=_('Marquer comme retenu'))
    def mark_as_accepted(self, request, queryset):
        updated = queryset.update(status='accepted')
        self.message_user(
            request,
            f"{updated} candidature(s) marquée(s) comme retenue(s).",
            messages.SUCCESS
        )

    @admin.action(description=_('Marquer comme rejeté'))
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(
            request,
            f"{updated} candidature(s) marquée(s) comme rejetée(s).",
            messages.SUCCESS
        )

    @admin.action(description=_('Remettre en attente'))
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(
            request,
            f"{updated} candidature(s) remise(s) en attente.",
            messages.SUCCESS
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('job_offer', 'user')
