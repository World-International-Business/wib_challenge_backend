from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Payment


class PaymentStatusFilter(admin.SimpleListFilter):
    title = _('Statut paiement')
    parameter_name = 'payment_status'

    def lookups(self, request, model_admin):
        return Payment.Status.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class PaymentPurposeFilter(admin.SimpleListFilter):
    title = _('Objet')
    parameter_name = 'purpose'

    def lookups(self, request, model_admin):
        return Payment.Purpose.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(purpose=self.value())
        return queryset


class RecentPaymentFilter(admin.SimpleListFilter):
    title = _('Période')
    parameter_name = 'recent_payment'

    def lookups(self, request, model_admin):
        return (
            ('24h', _('Dernières 24h')),
            ('7d', _('7 derniers jours')),
            ('30d', _('30 derniers jours')),
        )

    def queryset(self, request, queryset):
        if self.value() == '24h':
            return queryset.filter(created_at__gte=timezone.now() - timedelta(hours=24))
        elif self.value() == '7d':
            return queryset.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif self.value() == '30d':
            return queryset.filter(created_at__gte=timezone.now() - timedelta(days=30))
        return queryset


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_link', 'purpose_badge', 'course_or_certificate',
        'amount_display', 'provider_badge', 'status_badge',
        'paid_at_display', 'created_at'
    ]
    list_display_links = ['id', 'user_link']
    list_filter = [
        PaymentStatusFilter, PaymentPurposeFilter, 'provider',
        RecentPaymentFilter, 'created_at', 'paid_at'
    ]
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'provider_reference', 'course__title', 'certificate__verification_code'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'paid_at', 'provider_reference',
        'checkout_url', 'webhook_payload', 'webhook_signature',
        'payment_summary'
    ]
    date_hierarchy = 'created_at'
    list_per_page = 25
    actions = ['mark_as_succeeded', 'mark_as_failed', 'mark_as_cancelled', 'export_payments']

    fieldsets = (
        (_('👤 Utilisateur'), {
            'fields': ('user',)
        }),
        (_('💳 Objet du paiement'), {
            'fields': ('purpose', 'course', 'certificate')
        }),
        (_('💰 Montant'), {
            'fields': ('amount', 'currency')
        }),
        (_('🏦 Prestataire'), {
            'fields': ('provider', 'provider_reference', 'checkout_url')
        }),
        (_('📊 Statut'), {
            'fields': ('status', 'failure_reason', 'paid_at')
        }),
        (_('📋 Résumé'), {
            'fields': ('payment_summary',),
            'classes': ('collapse',)
        }),
        (_('🔧 Webhook'), {
            'fields': ('webhook_payload', 'webhook_signature'),
            'classes': ('collapse',)
        }),
        (_('📅 Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'course', 'certificate'
        )

    @admin.display(description=_('Utilisateur'), ordering='user__email')
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.pk])
            name = obj.user.get_full_name() or obj.user.email
            return format_html(
                '<a href="{}" style="color: #417690;"><strong>{}</strong></a><br><small>{}</small>',
                url, name, obj.user.email
            )
        return '-'

    @admin.display(description=_('Objet'))
    def purpose_badge(self, obj):
        colors = {
            Payment.Purpose.COURSE_ENROLLMENT: '#17a2b8',
            Payment.Purpose.CERTIFICATE: '#6f42c1',
        }
        icons = {
            Payment.Purpose.COURSE_ENROLLMENT: '📚',
            Payment.Purpose.CERTIFICATE: '🏆',
        }
        color = colors.get(obj.purpose, '#6c757d')
        icon = icons.get(obj.purpose, '📝')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px;">{} {}</span>',
            color, icon, obj.get_purpose_display()
        )

    @admin.display(description=_('Détail'))
    def course_or_certificate(self, obj):
        if obj.course:
            url = reverse('admin:learning_course_change', args=[obj.course.pk])
            return format_html('<a href="{}">{}</a>', url, obj.course.title)
        elif obj.certificate:
            return format_html('🏆 Certificat #{}', obj.certificate.pk)
        return '-'

    @admin.display(description=_('Montant'), ordering='amount')
    def amount_display(self, obj):
        return format_html(
            '<strong style="color: #28a745;">{} {}</strong>',
            obj.amount, obj.currency
        )

    @admin.display(description=_('Prestataire'))
    def provider_badge(self, obj):
        colors = {
            Payment.Provider.CINETPAY: '#fd7e14',
            Payment.Provider.STRIPE: '#635bff',
            Payment.Provider.PAYPAL: '#0070ba',
        }
        color = colors.get(obj.provider, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 11px;">{}</span>',
            color, obj.get_provider_display()
        )

    @admin.display(description=_('Statut'), ordering='status')
    def status_badge(self, obj):
        colors = {
            Payment.Status.PENDING: '#ffc107',
            Payment.Status.PROCESSING: '#17a2b8',
            Payment.Status.SUCCEEDED: '#28a745',
            Payment.Status.FAILED: '#dc3545',
            Payment.Status.CANCELLED: '#6c757d',
            Payment.Status.REFUNDED: '#fd7e14',
        }
        icons = {
            Payment.Status.PENDING: '⏳',
            Payment.Status.PROCESSING: '🔄',
            Payment.Status.SUCCEEDED: '✅',
            Payment.Status.FAILED: '❌',
            Payment.Status.CANCELLED: '🚫',
            Payment.Status.REFUNDED: '↩️',
        }
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '❓')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )

    @admin.display(description=_('Payé le'))
    def paid_at_display(self, obj):
        if obj.paid_at:
            return obj.paid_at.strftime('%d/%m/%Y %H:%M')
        return '-'

    @admin.display(description=_('Résumé du paiement'))
    def payment_summary(self, obj):
        return format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
            '<strong>Résumé:</strong><br>'
            '• Utilisateur: {}<br>'
            '• Objet: {}<br>'
            '• Montant: {} {}<br>'
            '• Prestataire: {}<br>'
            '• Statut: {}<br>'
            '• Référence: {}<br>'
            '</div>',
            obj.user.email if obj.user else '-',
            obj.get_purpose_display(),
            obj.amount, obj.currency,
            obj.get_provider_display(),
            obj.get_status_display(),
            obj.provider_reference or '-',
        )

    @admin.action(description=_('Marquer comme réussi'))
    def mark_as_succeeded(self, request, queryset):
        updated = queryset.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING]
        ).update(status=Payment.Status.SUCCEEDED, paid_at=timezone.now())
        self.message_user(request, f'{updated} paiement(s) marqué(s) comme réussi(s).')

    @admin.action(description=_('Marquer comme échoué'))
    def mark_as_failed(self, request, queryset):
        updated = queryset.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING]
        ).update(status=Payment.Status.FAILED)
        self.message_user(request, f'{updated} paiement(s) marqué(s) comme échoué(s).')

    @admin.action(description=_('Marquer comme annulé'))
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.exclude(
            status__in=[Payment.Status.SUCCEEDED, Payment.Status.REFUNDED]
        ).update(status=Payment.Status.CANCELLED)
        self.message_user(request, f'{updated} paiement(s) marqué(s) comme annulé(s).')

    @admin.action(description=_('Exporter en CSV'))
    def export_payments(self, request, queryset):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Utilisateur', 'Email', 'Objet', 'Cours/Certificat',
            'Montant', 'Devise', 'Prestataire', 'Référence', 'Statut',
            'Créé le', 'Payé le'
        ])

        for payment in queryset.select_related('user', 'course', 'certificate'):
            writer.writerow([
                payment.id,
                payment.user.get_full_name() if payment.user else '-',
                payment.user.email if payment.user else '-',
                payment.get_purpose_display(),
                payment.course.title if payment.course else
                (f'Certificat #{payment.certificate_id}' if payment.certificate else '-'),
                payment.amount,
                payment.currency,
                payment.get_provider_display(),
                payment.provider_reference or '-',
                payment.get_status_display(),
                payment.created_at.strftime('%d/%m/%Y %H:%M'),
                payment.paid_at.strftime('%d/%m/%Y %H:%M') if payment.paid_at else '-',
            ])

        return response

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        total = Payment.objects.count()
        succeeded = Payment.objects.filter(status=Payment.Status.SUCCEEDED).count()
        pending = Payment.objects.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING]
        ).count()
        failed = Payment.objects.filter(status=Payment.Status.FAILED).count()

        revenue = Payment.objects.filter(
            status=Payment.Status.SUCCEEDED
        ).aggregate(total=Sum('amount'))['total'] or 0

        extra_context.update({
            'total_payments': total,
            'succeeded_payments': succeeded,
            'pending_payments': pending,
            'failed_payments': failed,
            'total_revenue': revenue,
        })

        return super().changelist_view(request, extra_context=extra_context)
