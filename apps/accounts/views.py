import random

from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, OpenApiExample, extend_schema_view
from rest_framework import generics, viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404, GenericAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer, PasswordChangeSerializer, PasswordResetConfirmSerializer, \
    PasswordResetSerializer, UserRegisterResponse, PasswordResetResponseSerializer, GoogleLoginSerializer
from wib_challenge.permissions import IsSelf, ReadOnly
from wib_challenge.serializers import FieldErrorSerializer, SimpleMessageResponseSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Liste des utilisateurs",
        description="Récupère la liste paginée des utilisateurs actifs",
        tags=["Utilisateurs"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un utilisateur",
        description="Récupère les détails d'un utilisateur spécifique",
        tags=["Utilisateurs"]
    ),
    update=extend_schema(
        summary="Mettre à jour un utilisateur",
        description="Met à jour les informations d'un utilisateur",
        tags=["Utilisateurs"]
    ),
    partial_update=extend_schema(
        summary="Mise à jour partielle d'un utilisateur",
        description="Met à jour partiellement les informations d'un utilisateur",
        tags=["Utilisateurs"]
    ),
    destroy=extend_schema(
        summary="Supprimer un utilisateur",
        description="Supprime un utilisateur (soft delete)",
        tags=["Utilisateurs"]
    )
)
class UserViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsSelf | ReadOnly]

    def get_serializer_class(self, *args, **kwargs):
        if self.action == 'change_password':
            return PasswordChangeSerializer
        return UserSerializer

    def get_queryset(self):
        return self.queryset if self.request.user.is_staff else self.queryset.filter(is_active=True, is_staff=False)

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={status.HTTP_200_OK: SimpleMessageResponseSerializer,
                   status.HTTP_400_BAD_REQUEST: FieldErrorSerializer},
        summary="Changer le mot de passe",
        description="Change le mot de passe de l'utilisateur connecté",
        tags=["Authentification"],
        examples=[
            OpenApiExample(name='Incorrect password', description=_('Le mot de passe actuel est incorrect.'),
                           response_only=True, status_codes=(400,),
                           value={'old_password': {'detail': _('Le mot de passe actuel est incorrect.')}}, ),
            OpenApiExample(name='Same password',
                           description=_('Le nouveau mot de passe doit être différent de l\'ancien.'),
                           response_only=True, status_codes=(400,),
                           value={'new_password': {
                               'detail': _('Le nouveau mot de passe doit être différent de l\'ancien.')}}, ),
            OpenApiExample(name='Success', description=_('Success'), response_only=True, status_codes=(200,),
                           value={'detail': _('Mot de passe changé')}, ),
        ]
    )
    @action(detail=True, methods=['post'], url_path='change-password')
    def change_password(self, request, pk=None):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Informations du compte",
        description="Récupère les informations du compte de l'utilisateur connecté",
        tags=["Utilisateurs"]
    )
    @action(detail=False, methods=['get'], url_path='account')
    def account(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Utilisateur par username",
        description="Récupère un utilisateur par son username",
        tags=["Utilisateurs"]
    )
    @action(detail=False, methods=['get'], url_path='username/<str:username>')
    def username(self, request, username=None):
        user = get_object_or_404(self.get_queryset(), username=username)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


@extend_schema(
    responses=UserRegisterResponse,
    summary="Inscription d'un utilisateur",
    description="Crée un nouveau compte utilisateur et retourne les tokens d'authentification",
    tags=["Authentification"]
)
class RegisterUserView(generics.CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        token = TokenObtainPairSerializer(data={'email': request.data['email'], 'password': request.data['password']})
        token.is_valid(raise_exception=True)
        return Response(headers=response.headers, status=response.status_code,
                        data={**token.validated_data, 'data': response.data})


@extend_schema(
    responses={status.HTTP_200_OK: PasswordResetResponseSerializer, status.HTTP_400_BAD_REQUEST: FieldErrorSerializer},
    summary="Demande de réinitialisation de mot de passe",
    description="Envoie un email avec un code de vérification pour réinitialiser le mot de passe",
    tags=["Authentification"]
)
class PasswordResetView(GenericAPIView):
    permission_classes = []
    serializer_class = PasswordResetSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        value = serializer.validated_data['email']
        user = get_object_or_404(User.objects.filter(is_active=True), email=value)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        verification_code = random.randint(100000, 999999)
        context = {'verification_code': verification_code, 'uid': uid, 'token': token, }

        user.email_user(subject=_("Réinitialisation de mot de passe"),
                        message=render_to_string('accounts/password_reset_email.txt', context),
                        from_email="security@example.com",
                        html_message=render_to_string('accounts/password_reset_email.html', context), )

        return Response({'detail': _('Un email de réinitialisation de mot de passe vous a été envoyé.'), 'uidb64': uid,
                         'token': f'{token}|{verification_code}', 'verification_code': verification_code},
                        status=status.HTTP_200_OK)


@extend_schema(
    responses={status.HTTP_200_OK: SimpleMessageResponseSerializer, status.HTTP_400_BAD_REQUEST: FieldErrorSerializer},
    summary="Confirmation de réinitialisation de mot de passe",
    description="Confirme la réinitialisation du mot de passe avec le code de vérification",
    tags=["Authentification"]
)
class PasswordResetConfirmView(GenericAPIView):
    permission_classes = []
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, uidb64, token):
        try:
            token, verification_code = token.split('|')
            if int(verification_code) != int(request.data.get('verification_code')):
                return Response({"message": _("Code de vérification invalide")}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError, OverflowError):
            return Response({"message": _("Token invalide")}, status=status.HTTP_400_BAD_REQUEST)

        data = {'uidb64': uidb64, 'token': token, 'password': request.data.get('password'),
                # 'verification_code': request.data.get('verification_code')
                }
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response({"message": _("Mot de passe changé")}, status=status.HTTP_200_OK)


@extend_schema(
    responses={status.HTTP_200_OK: UserRegisterResponse},
    summary="Connexion Google",
    description="Authentification via Google OAuth et création/connexion automatique",
    tags=["Authentification"]
)
class GoogleLoginView(GenericAPIView):
    permission_classes = []
    serializer_class = GoogleLoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
