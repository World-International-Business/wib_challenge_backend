from typing import TYPE_CHECKING

from rest_framework.pagination import PageNumberPagination

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework import status
    from rest_framework.generics import GenericAPIView
    from rest_framework.response import Response
    from rest_framework.serializers import Serializer


class PageNumberAndSizePagination(PageNumberPagination):
    page_size = 20
    max_page_size = 200
    page_size_query_param = 'page_size'
    max_page_size_query_param = 'max_page_size'


def paginated_response(view: 'GenericAPIView', queryset: 'QuerySet', serializer: 'type[Serializer]', context=None):
    page = view.paginate_queryset(queryset)
    if page is not None:
        serializer = serializer(page, many=True, context=context)
        return view.get_paginated_response(serializer.data)

    serializer = serializer(queryset, many=True, context=context)
    return Response(serializer.data, status=status.HTTP_200_OK)
