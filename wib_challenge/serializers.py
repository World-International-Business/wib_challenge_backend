from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

SimpleMessageResponseSerializer = inline_serializer('SimpleMessageResponseSerializer', fields={
    'message': serializers.CharField(max_length=100)
})

ErrorSerializer = inline_serializer('ErrorSerializer', fields={
    'detail': serializers.CharField(max_length=100)
})

FieldErrorSerializer = inline_serializer('FieldErrorSerializer', fields={
    'field': ErrorSerializer,
})
