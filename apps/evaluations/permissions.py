from rest_framework import permissions


class RejectUnConstructedEvaluation(permissions.BasePermission):
    """
    Permission to reject evaluations that are not constructed.
    """

    def has_object_permission(self, request, view, obj):
        return obj.is_constructed


class IsSelfEvaluation(permissions.BasePermission):
    """
    Permission to only allow the creator of the evaluation to see it.
    """

    def has_object_permission(self, request, view, obj):
        return obj.publisher == request.user


class IsSelfCandidate(permissions.BasePermission):
    """
    Permission to only allow the candidate to see their own submission attempts.
    """

    def has_object_permission(self, request, view, obj):
        return obj.candidate_object_id == request.user.id
