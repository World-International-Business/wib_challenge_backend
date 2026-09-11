"""Template tags pour le dashboard admin global WIB Challenge."""
from django import template
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.simple_tag
def wib_dashboard_stats():
    """Récupère les statistiques globales des trois plateformes."""
    stats = {}

    try:
        from apps.accounts.models import User
        stats['total_users'] = User.objects.count()
        stats['active_users'] = User.objects.filter(is_active=True).count()
        stats['recent_users'] = User.objects.filter(
            date_joined__gte=timezone.now() - timedelta(days=7)
        ).count()
        stats['admin_users'] = User.objects.filter(is_staff=True).count()
    except Exception:
        stats['total_users'] = 0
        stats['active_users'] = 0
        stats['recent_users'] = 0
        stats['admin_users'] = 0

    try:
        from apps.evaluations.models import Evaluation, SubmissionAttempt, Participant
        from apps.evaluations.models import EvaluationType
        stats['total_evaluations'] = Evaluation.objects.count()
        stats['technical_evals'] = Evaluation.objects.filter(evaluation_type=EvaluationType.TECHNICAL).count()
        stats['logical_evals'] = Evaluation.objects.filter(evaluation_type=EvaluationType.LOGICAL).count()
        stats['personality_evals'] = Evaluation.objects.filter(evaluation_type=EvaluationType.PERSONALITY).count()
        stats['total_attempts'] = SubmissionAttempt.objects.count()
        stats['completed_attempts'] = SubmissionAttempt.objects.filter(
            submission__isnull=False, ended_at__isnull=False
        ).count()
        stats['total_participants'] = Participant.objects.count()
    except Exception:
        stats['total_evaluations'] = 0
        stats['technical_evals'] = 0
        stats['logical_evals'] = 0
        stats['personality_evals'] = 0
        stats['total_attempts'] = 0
        stats['completed_attempts'] = 0
        stats['total_participants'] = 0

    try:
        from apps.learning.models import Course, Certificate, CourseEnrollment, Progress
        stats['total_courses'] = Course.objects.count()
        stats['active_courses'] = Course.objects.filter(is_active=True).count()
        stats['total_certificates'] = Certificate.objects.count()
        stats['issued_certificates'] = Certificate.objects.filter(status='issued').count()
        stats['total_enrollments'] = CourseEnrollment.objects.count()
        stats['active_enrollments'] = CourseEnrollment.objects.filter(status='active').count()
        stats['completed_enrollments'] = CourseEnrollment.objects.filter(status='completed').count()
    except Exception:
        stats['total_courses'] = 0
        stats['active_courses'] = 0
        stats['total_certificates'] = 0
        stats['issued_certificates'] = 0
        stats['total_enrollments'] = 0
        stats['active_enrollments'] = 0
        stats['completed_enrollments'] = 0

    try:
        from apps.jobs.models import JobOffer, JobApplication
        stats['total_job_offers'] = JobOffer.objects.count()
        stats['published_job_offers'] = JobOffer.objects.filter(status='published').count()
        stats['active_job_offers'] = JobOffer.objects.filter(
            status='published', expires_at__gt=timezone.now()
        ).count()
        stats['total_applications'] = JobApplication.objects.count()
        stats['pending_applications'] = JobApplication.objects.filter(status='pending').count()
        stats['accepted_applications'] = JobApplication.objects.filter(status='accepted').count()
    except Exception:
        stats['total_job_offers'] = 0
        stats['published_job_offers'] = 0
        stats['active_job_offers'] = 0
        stats['total_applications'] = 0
        stats['pending_applications'] = 0
        stats['accepted_applications'] = 0

    try:
        from apps.payments.models import Payment
        stats['total_payments'] = Payment.objects.count()
        stats['succeeded_payments'] = Payment.objects.filter(status=Payment.Status.SUCCEEDED).count()
        stats['pending_payments'] = Payment.objects.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING]
        ).count()
        revenue = Payment.objects.filter(status=Payment.Status.SUCCEEDED).aggregate(
            total=Sum('amount')
        )['total']
        stats['total_revenue'] = float(revenue) if revenue else 0
    except Exception:
        stats['total_payments'] = 0
        stats['succeeded_payments'] = 0
        stats['pending_payments'] = 0
        stats['total_revenue'] = 0

    try:
        from apps.organizations.models import Organization, Notification, UserNotification
        stats['total_organizations'] = Organization.objects.count()
        stats['unread_org_notifications'] = Notification.objects.filter(is_read=False).count()
        stats['unread_user_notifications'] = UserNotification.objects.filter(is_read=False).count()
    except Exception:
        stats['total_organizations'] = 0
        stats['unread_org_notifications'] = 0
        stats['unread_user_notifications'] = 0

    try:
        from apps.candidates.models import CandidateProfile
        stats['total_candidate_profiles'] = CandidateProfile.objects.count()
        stats['open_to_work'] = CandidateProfile.objects.filter(open_to_work=True).count()
    except Exception:
        stats['total_candidate_profiles'] = 0
        stats['open_to_work'] = 0

    try:
        from apps.questions.models import Question
        stats['total_questions'] = Question.objects.count()
        stats['published_questions'] = Question.objects.filter(status='published').count()
    except Exception:
        stats['total_questions'] = 0
        stats['published_questions'] = 0

    return stats
