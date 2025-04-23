from rest_framework import permissions

from questions.models import Question


class RejectUnConstructedEvaluation(permissions.BasePermission):
    """
    Permission to reject evaluations that are not constructed.
    """

    def has_object_permission(self, request, view, obj):
        return obj.questions.filter(status=Question.Status.PUBLISHED).count() > 20

class IsSelfCandidate(permissions.BasePermission):
    """
    Permission to only allow the candidate to see their own submission attempts.
    """

    def has_object_permission(self, request, view, obj):
        return obj.candidate == request.user