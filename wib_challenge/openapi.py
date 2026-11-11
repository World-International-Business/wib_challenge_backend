import enum

from django.db import models
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class PermissiveJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'apps.core.authentication.PermissiveJWTAuthentication'
    name = 'jwtAuth'

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}


def _to_jsonable(value):
    if isinstance(value, (enum.Enum, models.Choices)):
        return value.value
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    return value


def stringify_enum_choices(result, **kwargs):
    return _to_jsonable(result)
