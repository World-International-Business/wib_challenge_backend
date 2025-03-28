from rest_framework import permissions

from questions.models import Question


class IsQuestionNotPending(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.status != Question.Status.PENDING
