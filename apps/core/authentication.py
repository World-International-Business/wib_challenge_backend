"""Authentication classes personnalisées.

PermissiveJWTAuthentication :
- Token valide       -> authentifie l'utilisateur
- Token expiré/invalid -> retourne None (utilisateur anonyme)
                       au lieu de lever une exception 401.

Cela permet aux endpoints publics (IsAuthenticatedOrReadOnly)
de rester accessibles même quand le frontend envoie un token expiré.
Les endpoints réellement protégés (IsAuthenticated) retourneront
toujours 401 car request.user sera AnonymousUser.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class PermissiveJWTAuthentication(JWTAuthentication):
    """JWTAuthentication qui n'échoue pas sur token expiré/invalid.

    Retourne (None, None) au lieu de lever une exception quand le token
    ne peut pas être validé. Les endpoints publics continuent de fonctionner,
    les endpoints protégés retourneront 401 via IsAuthenticated.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
        except (TokenError, InvalidToken):
            return None
        try:
            user = self.get_user(validated_token)
        except Exception:
            return None
        return (user, validated_token)
