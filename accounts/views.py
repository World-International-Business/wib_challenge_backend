import random

from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import generics, viewsets, status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404, GenericAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User
from accounts.serializers import UserListSerializer, UserSerializer, PasswordChangeSerializer, \
    PasswordResetConfirmSerializer, PasswordResetSerializer
from wib_challenge.permissions import IsSelf


class UserViewSet(viewsets.GenericViewSet, generics.RetrieveUpdateDestroyAPIView, generics.ListAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsSelf]

    def get_serializer_class(self, *args, **kwargs):
        if self.action == 'list':
            return UserListSerializer
        return UserSerializer

    def get_queryset(self):
        return self.queryset if self.request.user.is_staff else self.queryset.filter(is_active=False, is_staff=False)

    @extend_schema(
        request=PasswordChangeSerializer,
        examples=[
            OpenApiExample(
                name='Incorrect password',
                description=_('Le mot de passe actuel est incorrect.'),
                response_only=True,
                status_codes=(400,),
                value={
                    'old_password': {
                        'detail': _('Le mot de passe actuel est incorrect.')
                    }
                },
            ),
            OpenApiExample(
                name='Same password',
                description=_('Le nouveau mot de passe doit être différent de l\'ancien.'),
                response_only=True,
                status_codes=(400,),
                value={
                    'new_password': {
                        'detail': _('Le nouveau mot de passe doit être différent de l\'ancien.')
                    }
                },
            ),
            OpenApiExample(
                name='Success',
                description=_('Success'),
                response_only=True,
                status_codes=(200,),
                value={'detail': _('Mot de passe changé')},
            ),
        ]
    )
    @action(detail=True, methods=['post'], url_path='change-password')
    def change_password(self, request, pk=None):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class RegisterUser(generics.CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        token = TokenObtainPairSerializer(data={'email': request.data['email'], 'password': request.data['password']})
        token.is_valid(raise_exception=True)
        return Response(
            headers=response.headers,
            status=response.status_code,
            data={**token.validated_data, **response.data}
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
        context = {
            'verification_code': verification_code,
            'uid': uid,
            'token': token,
        }

        user.email_user(
            subject=_("Réinitialisation de mot de passe"),
            message=render_to_string('accounts/password_reset_email.txt', context),
            from_email="security@example.com",
            html_message=render_to_string('accounts/password_reset_email.html', context),
        )

        return Response({
            'detail': _('Un email de réinitialisation de mot de passe vous a été envoyé.'),
            'uid': uid,
            'token': f'{token}|{verification_code}',
            'verification_code': verification_code
        },
            status=status.HTTP_200_OK
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

        data = {
            'uid': uidb64,
            'token': token,
            'password': request.data.get('password'),
            'verification_code': request.data.get('verification_code')
        }
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response({"message": _("Mot de passe changé")}, status=status.HTTP_200_OK)
