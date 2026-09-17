from django.contrib import admin

from .models import AcademicClass, Exam, ExamAnswer, ExamAttempt, ExamQuestion, School, SchoolStaff, Student, Subject


class SchoolScopedAdmin(admin.ModelAdmin):
    manager_only = False

    def has_module_permission(self, request):
        return request.user.is_superuser or bool(self._staff_school(request))

    def _staff_school(self, request):
        staff = getattr(request.user, 'school_staff', None)
        return staff.school if staff and staff.is_active else None

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        school = self._staff_school(request)
        if request.user.is_superuser:
            return queryset
        if school is None:
            return queryset.none()
        return queryset.filter(school=school)

    def has_add_permission(self, request):
        return self._can_manage(request)

    def _can_manage(self, request):
        if request.user.is_superuser:
            return True
        staff = getattr(request.user, 'school_staff', None)
        return bool(staff and staff.is_active and (not self.manager_only or staff.role == SchoolStaff.Role.MANAGER))

    def has_change_permission(self, request, obj=None):
        return self._can_manage(request)

    def has_view_permission(self, request, obj=None):
        return self._can_manage(request)

    def has_delete_permission(self, request, obj=None):
        return self._can_manage(request)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    prepopulated_fields = {'code': ('name',)}

    def has_module_permission(self, request):
        return request.user.is_superuser


@admin.register(SchoolStaff)
class SchoolStaffAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'role', 'is_active']
    list_filter = ['school', 'role', 'is_active']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'school__name']
    autocomplete_fields = ['user', 'school']

    def save_model(self, request, obj, form, change):
        obj.user.is_staff = True
        obj.user.save(update_fields=['is_staff'])
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return request.user.is_superuser


@admin.register(AcademicClass)
class AcademicClassAdmin(SchoolScopedAdmin):
    manager_only = True
    list_display = ['name', 'level', 'school', 'academic_year']
    list_filter = ['school', 'level', 'academic_year']
    search_fields = ['name', 'level', 'academic_year']
    autocomplete_fields = ['school', 'teachers']


@admin.register(Student)
class StudentAdmin(SchoolScopedAdmin):
    manager_only = True
    list_display = ['user', 'school', 'academic_class', 'student_number', 'is_active']
    list_filter = ['school', 'academic_class', 'is_active']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'student_number']
    autocomplete_fields = ['user', 'school', 'academic_class']


@admin.register(Subject)
class SubjectAdmin(SchoolScopedAdmin):
    manager_only = True
    list_display = ['name', 'code', 'school']
    list_filter = ['school']
    search_fields = ['name', 'code']
    autocomplete_fields = ['school']


class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 1
    autocomplete_fields = ['question']


@admin.register(Exam)
class ExamAdmin(SchoolScopedAdmin):
    list_display = ['title', 'school', 'academic_class', 'subject', 'starts_at', 'ends_at', 'is_published', 'results_published']
    list_filter = ['school', 'subject', 'is_published', 'grading_scale']
    search_fields = ['title', 'academic_class__name', 'subject__name']
    autocomplete_fields = ['school', 'academic_class', 'subject', 'created_by']
    inlines = [ExamQuestionInline]


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ['exam', 'question', 'points', 'position']
    list_filter = ['exam__school', 'exam']
    search_fields = ['exam__title', 'question__title']
    autocomplete_fields = ['exam', 'question']

    def has_module_permission(self, request):
        staff = getattr(request.user, 'school_staff', None)
        return request.user.is_superuser or bool(staff and staff.is_active)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        staff = getattr(request.user, 'school_staff', None)
        if request.user.is_superuser:
            return queryset
        if not staff or not staff.is_active:
            return queryset.none()
        return queryset.filter(exam__school=staff.school)

    def has_add_permission(self, request):
        staff = getattr(request.user, 'school_staff', None)
        return request.user.is_superuser or bool(staff and staff.is_active)

    def has_view_permission(self, request, obj=None):
        staff = getattr(request.user, 'school_staff', None)
        return request.user.is_superuser or bool(staff and staff.is_active)

    def has_change_permission(self, request, obj=None):
        return self.has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_add_permission(request)


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['exam', 'student', 'attempt_number', 'status', 'score', 'fraud_flag', 'submitted_at']
    list_filter = ['exam__school', 'status', 'fraud_flag', 'exam']
    search_fields = ['exam__title', 'student__user__email', 'student__user__last_name']
    readonly_fields = ['started_at', 'expires_at', 'submitted_at', 'score', 'started_ip', 'submitted_ip', 'user_agent', 'integrity_events']
    autocomplete_fields = ['exam', 'student']

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    has_add_permission = has_change_permission = has_delete_permission = has_view_permission


@admin.register(ExamAnswer)
class ExamAnswerAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'exam_question', 'is_correct', 'points_awarded']
    list_filter = ['is_correct', 'attempt__exam__school']
    search_fields = ['attempt__student__user__email', 'exam_question__question__title']
    autocomplete_fields = ['attempt', 'exam_question']

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    has_add_permission = has_change_permission = has_delete_permission = has_view_permission
