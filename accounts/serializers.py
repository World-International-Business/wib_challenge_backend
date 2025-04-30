from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import make_password
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User


class WithUserTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        data = super().validate(attrs)
        data['data'] = UserSerializer(self.user).data
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


UserRegisterResponse = inline_serializer('UserRegisterResponse', fields={
    'access': serializers.CharField(),
    'refresh': serializers.CharField(),
    'data': UserSerializer()
})
