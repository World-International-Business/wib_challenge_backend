from django.db import transaction
from django.utils import timezone

from apps.learning.models import Content, Course, CourseEnrollment, Progress, Quiz


def compute_course_progress(user, course: Course, enrollment: CourseEnrollment = None):
    if enrollment is None:
        try:
            enrollment = CourseEnrollment.objects.get(user=user, course=course, status=CourseEnrollment.Status.ACTIVE)
        except CourseEnrollment.DoesNotExist:
            enrollment = None

    total_contents = Content.objects.filter(
        module__course=course, is_active=True, is_required=True
    ).count()
    completed_contents = Progress.objects.filter(
        user=user,
        content__module__course=course,
        content__is_required=True,
        is_completed=True,
    ).count() if enrollment else 0

    total_quizzes = Quiz.objects.filter(
        module__course=course, is_active=True
    ).count()
    completed_quizzes = enrollment.quiz_results.filter(
        is_passed=True
    ).count() if enrollment and hasattr(enrollment, 'quiz_results') else 0

    total_items = total_contents + total_quizzes
    completed_items = completed_contents + completed_quizzes
    percentage = round((completed_items / total_items * 100), 2) if total_items > 0 else 0
    is_completed = total_items > 0 and completed_items >= total_items

    return {
        'percentage': percentage,
        'completed_contents': completed_contents,
        'total_contents': total_contents,
        'completed_quizzes': completed_quizzes,
        'total_quizzes': total_quizzes,
        'is_completed': is_completed,
    }


def get_next_content(user, course: Course):
    if not user.is_authenticated:
        return None

    completed_ids = Progress.objects.filter(
        user=user, is_completed=True, content__module__course=course
    ).values_list('content_id', flat=True)

    next_content = Content.objects.filter(
        module__course=course, is_active=True
    ).exclude(id__in=completed_ids).order_by('module__order', 'order', 'id').first()

    if next_content:
        return {
            'id': next_content.id,
            'moduleId': next_content.module_id,
            'contentType': next_content.content_type,
            'title': next_content.title,
        }
    return None


def complete_content(user, content: Content, enrollment: CourseEnrollment = None):
    if enrollment is None:
        enrollment = CourseEnrollment.objects.get(
            user=user,
            course=content.module.course,
            status=CourseEnrollment.Status.ACTIVE,
        )

    progress, created = Progress.objects.get_or_create(
        user=user,
        content=content,
        defaults={
            'enrollment': enrollment,
            'is_completed': True,
            'completed_at': timezone.now(),
        },
    )

    if not created and not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save(update_fields=['is_completed', 'completed_at', 'updated_at'])

    course_progress = compute_course_progress(user, content.module.course, enrollment)
    next_content = get_next_content(user, content.module.course)

    if course_progress['is_completed'] and enrollment.status != CourseEnrollment.Status.COMPLETED:
        enrollment.status = CourseEnrollment.Status.COMPLETED
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=['status', 'completed_at', 'updated_at'])

    return {
        'contentProgress': {
            'contentId': content.id,
            'isCompleted': progress.is_completed,
            'completedAt': progress.completed_at,
        },
        'courseProgress': course_progress,
        'nextContent': next_content,
    }


def compute_blocking_reasons(user, course: Course):
    reasons = []
    required_contents = Content.objects.filter(module__course=course, is_active=True, is_required=True)
    completed_ids = Progress.objects.filter(
        user=user, content__module__course=course, is_completed=True
    ).values_list('content_id', flat=True)

    for content in required_contents:
        if content.id not in completed_ids:
            reasons.append({
                'type': 'content_not_completed',
                'contentId': content.id,
                'moduleId': content.module_id,
                'label': f"Terminer le contenu \"{content.title}\"",
            })

    quizzes = Quiz.objects.filter(module__course=course, is_active=True)
    for quiz in quizzes:
        if not quiz.quiz_results.filter(user=user, is_passed=True).exists():
            reasons.append({
                'type': 'quiz_not_passed',
                'moduleId': quiz.module_id,
                'quizId': quiz.id,
                'label': f"Valider le quiz du module {quiz.module.order or quiz.module_id}",
            })

    return reasons
