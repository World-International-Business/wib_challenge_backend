from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ('password', 'groups', 'user_permissions', 'is_staff', 'is_superuser')

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'role', 'is_active', 'picture', 'email', 'first_name', 'last_name', 'date_joined', 'last_login')

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("Il n'existe pas d'utilisateur avec cet email."))

        if not user.is_active:
            raise serializers.ValidationError(_("Cet utilisateur est désactivé."))

        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(min_length=8)

    def validate(self, attrs):
        try:
            uid = urlsafe_base64_decode(attrs['uidb64']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError(_("L'utilisateur n'existe pas."))

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError(_("Le token est expiré ou invalide."))

        user.set_password(attrs['password'])
        user.save()

        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_old_password(self, value):
        if not self.context['request'].user.is_staff:
            if not self.context['request'].user.check_password(value):
                raise serializers.ValidationError(_("Le mot de passe actuel est incorrect."))
        return value

    def validate_new_password(self, value):
        if self.context['request'].user.check_password(value):
            raise serializers.ValidationError(_("Le nouveau mot de passe doit être différent de l'ancien."))
        return value
