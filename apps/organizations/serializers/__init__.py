from rest_framework import serializers

from apps.organizations.models import Organization, Notification, UserNotification


class OrganizationSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = '__all__'

    def get_field_names(self, declared_fields, info):
        """Ajoute automatiquement le champ calculé logo_url au payload sérialisé.

        On garde fields = '__all__' pour tous les champs du modèle et on ajoute logo_url
        sans devoir les lister manuellement.
        """
        fields = super().get_field_names(declared_fields, info)
        if 'logo_url' not in fields:
            fields.append('logo_url')
        return fields

    def get_logo_url(self, obj):
        request = self.context.get('request') if hasattr(self, 'context') else None
        if not obj.logo:
            return None
        try:
            url = obj.logo.url
        except Exception:
            return None
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class UserNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = '__all__'
