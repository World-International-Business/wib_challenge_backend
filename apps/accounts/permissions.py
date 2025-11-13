from django.contrib.auth import get_user_model
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


class IsCreator(permissions.BasePermission):

    def has_permission(self, request, view):
        User = get_user_model()
        return request.user.is_authenticated and (request.user.role in [User.Roles.EVALUATOR, User.Roles.ADMIN,
          User.Roles.ORGANIZATION] or request.user.is_superuser)


class IsOrganization(permissions.BasePermission):

    def has_permission(self, request, view):
        User = get_user_model()
        return request.user.is_authenticated and (
                request.user.role in [User.Roles.ORGANIZATION, User.Roles.ADMIN] or request.user.is_superuser)
