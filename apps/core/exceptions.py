"""Exception handler personnalisé pour des messages d'erreur clairs en français.

Remplace les messages DRF standard (ex: "No Quiz matches the given query.")
par des messages compréhensibles pour l'utilisateur final.
"""
from rest_framework.views import exception_handler
from django.http import Http404


def custom_exception_handler(exc, context):
    """Exception handler qui produit des messages d'erreur clairs."""
    response = exception_handler(exc, context)

    # Personnaliser les erreurs 404 (objet introuvable)
    if isinstance(exc, Http404):
        # Récupère le nom du modèle depuis la view si possible
        view = context.get('view')
        model_name = "La ressource"
        if view and hasattr(view, 'queryset') and view.queryset is not None:
            model = view.queryset.model
            model_name = model._meta.verbose_name.capitalize()

        message = str(exc)
        # Remplacer les messages DRF standard par des messages clairs
        if 'matches the given query' in message or not message or 'Not found' in message:
            message = f"{model_name} introuvable ou plus disponible."

        from rest_framework.response import Response
        from rest_framework import status as http_status
        return Response(
            {'detail': message, 'code': 'not_found'},
            status=http_status.HTTP_404_NOT_FOUND
        )

    return response
