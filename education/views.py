from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from questions.models import Choice, Question

from .forms import ExamCreationForm, StudentCreationForm
from .models import AcademicClass, Exam, ExamAnswer, ExamAttempt, ExamQuestion, SchoolStaff, Student, Subject

User = get_user_model()


def _school_staff(request):
    staff = getattr(request.user, 'school_staff', None)
    return staff if staff and staff.is_active else None


def _is_school_staff(user):
    staff = getattr(user, 'school_staff', None)
    return bool(user.is_authenticated and staff and staff.is_active)


school_staff_required = user_passes_test(_is_school_staff)


def _allowed_classes(staff):
    classes = AcademicClass.objects.filter(school=staff.school)
    if staff.role == SchoolStaff.Role.TEACHER:
        classes = classes.filter(teachers=staff)
    return classes.distinct()


def _allowed_exam(staff, exam):
    return exam.school_id == staff.school_id and (
        staff.role == SchoolStaff.Role.MANAGER or exam.academic_class.teachers.filter(id=staff.id).exists()
    )


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR')


@login_required
def school_home_view(request):
    if _is_school_staff(request.user):
        return redirect('school_dashboard')
    if hasattr(request.user, 'student_profile'):
        return redirect('student_dashboard')
    return redirect('home')


@school_staff_required
def school_dashboard_view(request):
    staff = _school_staff(request)
    exams = Exam.objects.filter(school=staff.school).select_related('academic_class', 'subject').annotate(
        attempts_count=Count('attempts')
    )
    if staff.role == SchoolStaff.Role.TEACHER:
        exams = exams.filter(academic_class__teachers=staff)
    pending_attempts = ExamAttempt.objects.filter(
        exam__school=staff.school,
        status=ExamAttempt.Status.REVIEW,
    ).select_related('exam', 'student__user').order_by('-submitted_at')
    if staff.role == SchoolStaff.Role.TEACHER:
        pending_attempts = pending_attempts.filter(exam__academic_class__teachers=staff)

    return render(request, 'education/school_dashboard.html', {
        'staff': staff,
        'exams': exams.order_by('-created_at'),
        'students_count': Student.objects.filter(school=staff.school, is_active=True).count(),
        'classes_count': _allowed_classes(staff).count(),
        'pending_attempts': pending_attempts[:20],
    })


@school_staff_required
@transaction.atomic
def school_student_create_view(request):
    staff = _school_staff(request)
    form = StudentCreationForm(request.POST or None)
    form.fields['academic_class'].queryset = _allowed_classes(staff)
    if request.method == 'POST' and form.is_valid():
        if User.objects.filter(email__iexact=form.cleaned_data['email']).exists():
            form.add_error('email', 'Un compte utilise déjà cette adresse email.')
        else:
            academic_class = form.cleaned_data['academic_class']
            user = User.objects.create_user(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_active=True,
            )
            Student.objects.create(
                user=user,
                school=staff.school,
                academic_class=academic_class,
                student_number=form.cleaned_data['student_number'],
            )
            messages.success(request, f"Le compte de {user.get_full_name()} a été créé.")
            return redirect('school_dashboard')
    return render(request, 'education/student_create.html', {'form': form, 'staff': staff})


@school_staff_required
@transaction.atomic
def school_exam_create_view(request):
    staff = _school_staff(request)
    form = ExamCreationForm(request.POST or None)
    form.fields['academic_class'].queryset = _allowed_classes(staff)
    form.fields['subject'].queryset = Subject.objects.filter(school=staff.school)
    questions = Question.objects.filter(
        question_category=Question.QuestionCategory.NORMAL,
    ).select_related('category').prefetch_related('choices').order_by('category__name', 'title')
    if request.method == 'POST' and form.is_valid():
        selected_ids = request.POST.getlist('question_ids')
        selected_questions = list(questions.filter(id__in=selected_ids))
        if not selected_questions:
            form.add_error(None, 'Sélectionnez au moins une question.')
        else:
            exam = form.save(commit=False)
            exam.school = staff.school
            exam.created_by = request.user
            exam.save()
            ExamQuestion.objects.bulk_create([
                ExamQuestion(exam=exam, question=question, position=index)
                for index, question in enumerate(selected_questions, start=1)
            ])
            messages.success(request, 'L’épreuve a été créée en brouillon.')
            return redirect('school_dashboard')
    return render(request, 'education/exam_create.html', {
        'form': form,
        'questions': questions,
        'staff': staff,
    })


@school_staff_required
@transaction.atomic
def school_exam_publish_view(request, exam_id):
    staff = _school_staff(request)
    exam = get_object_or_404(Exam, id=exam_id, school=staff.school)
    if request.method != 'POST' or not _allowed_exam(staff, exam):
        raise Http404
    if not exam.exam_questions.exists():
        messages.error(request, 'Ajoutez au moins une question avant de publier l’épreuve.')
    else:
        exam.is_published = True
        exam.save(update_fields=['is_published'])
        messages.success(request, 'L’épreuve est maintenant visible par la classe concernée.')
    return redirect('school_dashboard')


@school_staff_required
@transaction.atomic
def school_exam_results_publish_view(request, exam_id):
    staff = _school_staff(request)
    exam = get_object_or_404(Exam, id=exam_id, school=staff.school)
    if request.method != 'POST' or not _allowed_exam(staff, exam):
        raise Http404
    exam.results_published = True
    exam.save(update_fields=['results_published'])
    messages.success(request, 'Les résultats sont maintenant visibles par les élèves.')
    return redirect('school_dashboard')


@login_required
def student_dashboard_view(request):
    student = getattr(request.user, 'student_profile', None)
    if not student or not student.is_active:
        return redirect('home')
    now = timezone.now()
    exams = Exam.objects.filter(
        school=student.school,
        academic_class=student.academic_class,
        is_published=True,
    ).select_related('subject')
    exam_rows = []
    for exam in exams:
        attempts = list(exam.attempts.filter(student=student).order_by('-attempt_number'))
        active = next((attempt for attempt in attempts if attempt.status == ExamAttempt.Status.IN_PROGRESS), None)
        exam_rows.append({
            'exam': exam,
            'attempts_used': len(attempts),
            'active_attempt': active,
            'can_start': active is not None or len(attempts) < exam.max_attempts,
            'is_open': exam.starts_at <= now <= exam.ends_at,
            'latest': attempts[0] if attempts else None,
        })
    return render(request, 'education/student_dashboard.html', {
        'student': student,
        'exam_rows': exam_rows,
    })


@login_required
@transaction.atomic
def school_exam_attempt_view(request, exam_id):
    student = getattr(request.user, 'student_profile', None)
    if not student or not student.is_active:
        return redirect('home')
    now = timezone.now()
    exam = get_object_or_404(
        Exam.objects.prefetch_related('exam_questions__question__choices'),
        id=exam_id,
        school=student.school,
        academic_class=student.academic_class,
        is_published=True,
    )
    existing = exam.attempts.filter(student=student, status=ExamAttempt.Status.IN_PROGRESS).first()
    if existing:
        attempt = existing
    else:
        if not (exam.starts_at <= now <= exam.ends_at):
            messages.info(request, 'Cette épreuve n’est pas ouverte.')
            return redirect('student_dashboard')
        attempt_number = exam.attempts.filter(student=student).count() + 1
        if attempt_number > exam.max_attempts:
            messages.warning(request, 'Le nombre maximal de tentatives est atteint.')
            return redirect('student_dashboard')
        expires_at = min(now + timedelta(minutes=exam.duration_minutes), exam.ends_at)
        attempt = ExamAttempt.objects.create(
            exam=exam,
            student=student,
            attempt_number=attempt_number,
            expires_at=expires_at,
            started_ip=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    if request.method == 'POST':
        for exam_question in exam.exam_questions.all():
            answer, _ = ExamAnswer.objects.get_or_create(attempt=attempt, exam_question=exam_question)
            selected_ids = request.POST.getlist(f'question_{exam_question.id}')
            answer.text = request.POST.get(f'text_{exam_question.id}', '').strip()
            answer.selected_choices.set(
                Choice.objects.filter(id__in=selected_ids, question=exam_question.question)
            )
            if exam_question.question.is_open_answer:
                answer.is_correct = None
                answer.points_awarded = 0
            else:
                expected = set(exam_question.question.choices.filter(is_correct=True).values_list('id', flat=True))
                actual = set(answer.selected_choices.values_list('id', flat=True))
                answer.is_correct = actual == expected and bool(expected)
                answer.points_awarded = exam_question.points if answer.is_correct else 0
            answer.save()

        attempt.submitted_at = now
        attempt.submitted_ip = _client_ip(request)
        has_open_answers = exam.exam_questions.filter(question__question_type=Question.QuestionType.OPEN_ANSWER).exists()
        attempt.status = ExamAttempt.Status.REVIEW if has_open_answers else ExamAttempt.Status.CORRECTED
        total_points = exam.exam_questions.aggregate(total=models.Sum('points'))['total'] or 0
        earned_points = sum(answer.points_awarded for answer in attempt.answers.all())
        attempt.score = (earned_points / total_points * exam.grading_scale) if total_points else 0
        attempt.save(update_fields=['submitted_at', 'submitted_ip', 'status', 'score'])
        messages.success(request, 'Votre épreuve a été envoyée.')
        return redirect('student_dashboard')

    return render(request, 'education/exam_attempt.html', {
        'exam': exam,
        'attempt': attempt,
        'remaining_seconds': max(0, int((attempt.expires_at - now).total_seconds())),
    })


@login_required
def school_exam_integrity_event_view(request, attempt_id):
    student = getattr(request.user, 'student_profile', None)
    if request.method != 'POST' or not student:
        return JsonResponse({'error': 'Accès refusé.'}, status=403)
    attempt = get_object_or_404(
        ExamAttempt,
        id=attempt_id,
        student=student,
        status=ExamAttempt.Status.IN_PROGRESS,
    )
    event_name = request.POST.get('event', '').strip()
    allowed_events = {'tab_hidden', 'fullscreen_exit', 'copy_attempt', 'paste_attempt'}
    if event_name not in allowed_events:
        return JsonResponse({'error': 'Événement inconnu.'}, status=400)
    events = list(attempt.integrity_events or [])
    events.append({
        'event': event_name,
        'at': timezone.now().isoformat(),
        'ip': _client_ip(request),
    })
    attempt.integrity_events = events
    attempt.fraud_flag = True
    attempt.fraud_reason = 'Événement(s) d’intégrité à vérifier par l’enseignant.'
    attempt.save(update_fields=['integrity_events', 'fraud_flag', 'fraud_reason'])
    return JsonResponse({'ok': True})


@school_staff_required
@transaction.atomic
def school_attempt_grade_view(request, attempt_id):
    staff = _school_staff(request)
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related('exam', 'student__user').prefetch_related('answers__exam_question__question'),
        id=attempt_id,
        exam__school=staff.school,
    )
    if not _allowed_exam(staff, attempt.exam):
        raise Http404
    if request.method == 'POST':
        for answer in attempt.answers.select_related('exam_question').all():
            if not answer.exam_question.question.is_open_answer:
                continue
            try:
                points = float(request.POST.get(f'points_{answer.id}', 0))
            except (TypeError, ValueError):
                points = 0
            points = max(0, min(points, answer.exam_question.points))
            answer.points_awarded = points
            answer.is_correct = points > 0
            answer.save(update_fields=['points_awarded', 'is_correct'])
        total_points = sum(item.exam_question.points for item in attempt.answers.select_related('exam_question'))
        earned_points = sum(item.points_awarded for item in attempt.answers.all())
        attempt.score = (earned_points / total_points * attempt.exam.grading_scale) if total_points else 0
        attempt.status = ExamAttempt.Status.CORRECTED
        attempt.save(update_fields=['score', 'status'])
        messages.success(request, 'La copie a été corrigée.')
        return redirect('school_dashboard')
    return render(request, 'education/attempt_grade.html', {'attempt': attempt, 'staff': staff})
