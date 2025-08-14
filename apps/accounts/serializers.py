import json
import mimetypes
import urllib.request
import uuid
from traceback import print_exception

from decouple import config
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.files.base import ContentFile
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import inline_serializer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


class WithUserTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        data = super().validate(attrs)
        data['data'] = UserSerializer(self.user, context=self.context).data
        return data


class PublisherSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'picture', 'full_name']
        read_only_fields = ['id', 'username', 'role', 'picture']


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.PrimaryKeyRelatedField(read_only=True)
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = User
        exclude = ('groups', 'user_permissions', 'is_superuser')
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_active']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_role(self, value):
        if value == User.Roles.ADMIN:
            raise serializers.ValidationError(
                _("Vous ne pouvez pas créer un compte admin."))
        return value

    def create(self, validated_data):
        from django.db import transaction
        with transaction.atomic():
            return User.objects.create_user(**validated_data)


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                _("Il n'existe pas d'utilisateur avec cet email."))

        if not user.is_active:
            raise serializers.ValidationError(
                _("Cet utilisateur est désactivé."))

        return value


PasswordResetResponseSerializer = inline_serializer('PasswordResetResponseSerializer', fields={
    'detail': serializers.CharField(),
    'uidb64': serializers.CharField(),
    'token': serializers.CharField(),
    'verification_code': serializers.IntegerField()
})


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(min_length=8)

    def validate(self, attrs):
        try:
            uid = urlsafe_base64_decode(attrs['uidb64']).decode()
            user = User.objects.filter(pk=uid).only('id').first()

            if not user:
                raise serializers.ValidationError(
                    _("L'utilisateur n'existe pas."))

            if not default_token_generator.check_token(user, attrs['token']):
                raise serializers.ValidationError(
                    _("Le token est expiré ou invalide."))

            User.objects.filter(pk=uid).update(
                password=make_password(attrs['password']))

        except (TypeError, ValueError, OverflowError):
            raise serializers.ValidationError(_("L'utilisateur n'existe pas."))

        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_old_password(self, value):
        if self.context['request'].user.is_staff:
            return value

        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError(
                _("Le mot de passe actuel est incorrect."))
        return value

    def validate_new_password(self, value):
        if self.context['request'].user.check_password(value):
            raise serializers.ValidationError(
                _("Le nouveau mot de passe doit être différent de l'ancien."))
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])

    @property
    def data(self):
        return {'message': _('Mot de passe changé')}


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=User.Roles.choices, required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        id_token_str = attrs.get('id_token')
        role = attrs.get('role', User.Roles.USER)

        if role and role == User.Roles.ADMIN:
            raise ValidationError("Vous ne pouvez pas créer un compte admin.")

        try:
            info = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                audience=config('GOOGLE_OAUTH_CLIENT_ID')
            )

            print(info, json.dumps(info, indent=2))

            email = info.get('email')

            if not email:
                raise ValidationError("Email introuvable dans le token")
            elif not User.objects.filter(email=email).exists() and not role:
                raise ValidationError("Vous devez choisir un rôle avant de vous connecter")

            user, created = User.objects.get_or_create(email=email, defaults={
                "username": uuid.UUID(int=int(info.get('sub')), version=4) if info.get('sub') else None,
                "first_name": info.get('given_name', info.get('name', '')).capitalize(),
                'last_name': info.get('family_name', '').capitalize(),
                "role": role
            })

            picture: str = info.get('picture', None)
            if created and picture is not None:
                picture = (picture[:picture.rfind('=')] if '=' in picture else picture) + '=s1024-nu-c-d'
                response = urllib.request.urlopen(picture)
                ext = mimetypes.guess_extension(response.info().get_content_type())
                if ext is None:
                    ext = '.png'
                file = info.get('sub') + ext
                user.picture.save(name=file, content=ContentFile(response.read()))

            refresh = RefreshToken.for_user(user)

            return {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "data": UserSerializer(user, context=self.context).data
            }
        except ValueError as e:
            print_exception(e)
            raise ValidationError("Token invalide")
        except Exception as e:
            raise ValidationError(str(e))


UserRegisterResponse = inline_serializer('UserRegisterResponse', fields={
    'access': serializers.CharField(),
    'refresh': serializers.CharField(),
    'data': UserSerializer()
})
