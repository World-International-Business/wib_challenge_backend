from rest_framework.permissions import BasePermission


class IsSelf(BasePermission):

    def has_object_permission(self, request, view, obj):
        return bool(request.user == obj)


class IsOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return bool(request.user == obj.user)
        elif hasattr(obj, 'profile'):
            return bool(request.user == obj.profile.user)
        else:
            return False


class ReadOnly(BasePermission):

    def has_permission(self, request, view):
        return request.method in ['GET', 'HEAD', 'OPTIONS']

    def has_object_permission(self, request, view, obj):
        return request.method in ['GET', 'HEAD', 'OPTIONS']
