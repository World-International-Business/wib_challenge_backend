from rest_framework import permissions


class IsCompanyOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission personnalisée pour permettre uniquement aux propriétaires
    de l'organisation de modifier leurs offres d'emploi.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if hasattr(request.user, 'organization'):
            return obj.company == request.user.organization

        return False


class CanAccessJobApplication(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return (
            request.user.is_staff
            or obj.user_id == request.user.id
            or (
                hasattr(request.user, 'organization')
                and obj.job_offer.company_id == request.user.organization.id
            )
        )
