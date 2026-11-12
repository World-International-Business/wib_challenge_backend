from rest_framework import serializers

from apps.organizations.models import Organization, Notification, UserNotification

KNOWN_CHANNELS = {'site_carriere', 'linkedin', 'emploi_cm'}


class OrganizationSerializer(serializers.ModelSerializer):
    preferred_channels = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = Organization
        fields = '__all__'

    def validate_preferred_channels(self, value):
        # Ignore silencieusement les canaux inconnus et les doublons ; liste vide tolérée
        return list(dict.fromkeys(c for c in value if c in KNOWN_CHANNELS))


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class UserNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = '__all__'
