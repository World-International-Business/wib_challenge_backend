from rest_framework import permissions

from apps.accounts.models import User


class IsOrganization(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est une organisation
    """

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role == User.Roles.ORG and
                hasattr(request.user, 'organization')
                )
