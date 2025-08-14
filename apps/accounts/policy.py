from rest_access_policy import AccessPolicy, Statement


class UserAccountPolicy(AccessPolicy):
    statements = [
        Statement(
            action=['list', 'retrieve', 'username'],
            principal=['*'],
            effect='allow',
        ),
        Statement(
            action=['change_password'],
            principal=['authenticated'],
            effect='allow',
            condition='is_self',
        ),
        Statement(
            action=['update', 'partial_update', 'destroy'],
            principal=['authenticated'],
            effect='allow',
            condition='is_self_or_admin',
        ),
        Statement(
            action=['account'],
            principal=['authenticated'],
            effect='allow',
        ),
    ]

    @classmethod
    def scope_queryset(cls, request, qs):
        return qs if request.user.is_staff else qs.filter(is_active=True, is_staff=False)

    def is_self(self, request, view, action):
        return request.user == view.get_object()

    def is_self_or_admin(self, request, view, action):
        return request.user == view.get_object() or request.user.is_admin or request.user.is_superuser
