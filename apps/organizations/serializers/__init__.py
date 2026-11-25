from rest_framework import serializers

from apps.organizations.models import Organization, Notification, UserNotification

KNOWN_CHANNELS = {'site_carriere', 'linkedin', 'emploi_cm'}


class OrganizationSerializer(serializers.ModelSerializer):
    preferred_channels = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = Organization
        fields = '__all__'
        read_only_fields = ['auto_analyze_applications', 'notify_blocking_cases']

    def validate_preferred_channels(self, value):
        # Ignore silencieusement les canaux inconnus et les doublons ; liste vide tolérée
        return list(dict.fromkeys(c for c in value if c in KNOWN_CHANNELS))


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            raise serializers.ValidationError('Un booléen JSON true ou false est requis.')
        return data


class AgentSettingsSerializer(serializers.ModelSerializer):
    auto_analyze_applications = StrictBooleanField(required=False)
    notify_blocking_cases = StrictBooleanField(required=False)
    require_human_approval_for_rejection = StrictBooleanField(
        required=False, help_text='Toujours true : validation humaine obligatoire et non désactivable avant tout refus.')

    class Meta:
        model = Organization
        fields = ['auto_analyze_applications', 'notify_blocking_cases', 'require_human_approval_for_rejection']

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: 'Champ inconnu.' for key in sorted(unknown)})
        return super().to_internal_value(data)

    def validate_require_human_approval_for_rejection(self, value):
        if not value:
            raise serializers.ValidationError('La validation humaine avant tout refus est obligatoire et ne peut pas être désactivée.')
        return value

    def update(self, instance, validated_data):
        validated_data.pop('require_human_approval_for_rejection', None)
        return super().update(instance, validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class UserNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = '__all__'
