from apps.accounts.models import User


def user_must_be(request, view, action, field: str) -> bool:
    account = view.get_object()
    return getattr(account, field) == request.user


def is_owner_through(request, view, action, field: str) -> bool:
    return hasattr(view.get_object(), field) and request.user == getattr(view.get_object(), field)


def is_creator(request, view, action) -> bool:
    return request.user.role in [User.Roles.EVALUATOR, User.Roles.ADMIN,
                                 User.Roles.ORGANIZATION] or request.user.is_superuser


def is_developer(request, view, action) -> bool:
    return request.user.role == User.Roles.USER
