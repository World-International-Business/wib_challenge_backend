from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.jobs.models import JobOffer
from apps.organizations.models import RecruitmentEmailInbox, RecruitmentEmailMessage
from apps.organizations.serializers import StrictBooleanField
from services.channel_crypto import encrypt_secret


class EmailInboxSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, max_length=1024)
    enabled = StrictBooleanField(required=False)
    default_offer = serializers.PrimaryKeyRelatedField(queryset=JobOffer.objects.none(), required=False, allow_null=True)
    pending_assignment_count = serializers.IntegerField(read_only=True, default=0)
    pending_analysis_count = serializers.IntegerField(read_only=True, default=0)
    sync_status = serializers.SerializerMethodField()

    class Meta:
        model = RecruitmentEmailInbox
        fields = ['id', 'provider', 'host', 'username', 'password', 'folder', 'default_offer', 'enabled',
                  'verified_at', 'last_sync_at', 'next_sync_at', 'error_code',
                  'pending_assignment_count', 'pending_analysis_count', 'sync_status', 'created_at']
        read_only_fields = ['id', 'provider', 'verified_at', 'last_sync_at', 'next_sync_at', 'error_code', 'created_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context.get('request').user if self.context.get('request') else None
        organization = getattr(user, 'organization', None)
        if organization:
            self.fields['default_offer'].queryset = JobOffer.objects.filter(company=organization)

    def get_sync_status(self, obj) -> str:
        if obj.error_code:
            return 'error'
        if not obj.verified_at:
            return 'unverified'
        if not obj.enabled:
            return 'disabled'
        if obj.locked_until and obj.locked_until > timezone.now():
            return 'syncing'
        if not obj.last_sync_at:
            return 'waiting'
        return 'stale' if obj.last_sync_at < timezone.now() - timedelta(minutes=5) else 'active'

    def validate_host(self, value):
        value = value.strip().lower().rstrip('.')
        if not value or any(character not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for character in value):
            raise serializers.ValidationError('Nom DNS du serveur IMAP requis, sans URL ni port. TLS sur le port 993 uniquement.')
        return value

    def validate_folder(self, value):
        if not value.isascii() or any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise serializers.ValidationError('Utilisez un nom de dossier IMAP ASCII sans caractères de contrôle.')
        return value

    def validate_username(self, value):
        if any(ord(character) < 32 for character in value):
            raise serializers.ValidationError('Identifiant IMAP invalide.')
        return value

    def validate(self, attrs):
        is_gmail = self.instance and self.instance.provider == RecruitmentEmailInbox.Provider.GMAIL
        if self.instance:
            for key in ['host', 'username', 'folder']:
                if key in attrs and attrs[key] != getattr(self.instance, key):
                    raise serializers.ValidationError({key: 'Créez une nouvelle connexion pour changer la boîte ou le dossier ; désactivez l’ancienne.'})
            if 'password' in attrs and is_gmail:
                raise serializers.ValidationError({'password': 'Connexion OAuth : reconnectez la boîte via Google, sans mot de passe.'})
        elif not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Un mot de passe d’application IMAP est requis.'})
        if attrs.get('enabled') and (not self.instance or not self.instance.verified_at or 'password' in attrs):
            raise serializers.ValidationError({'enabled': 'Testez la connexion avant de l’activer.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['secret'] = encrypt_secret(password)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password is not None:
            validated_data.update(secret=encrypt_secret(password), verified_at=None, enabled=False)
        return super().update(instance, validated_data)


class EmailMessageSerializer(serializers.ModelSerializer):
    application_id = serializers.IntegerField(read_only=True)
    analysis_status = serializers.CharField(source='application.analysis.status', read_only=True, default=None)
    match_score = serializers.IntegerField(source='application.match_score', read_only=True, default=None)
    needs_human_review = serializers.BooleanField(source='application.needs_human_review', read_only=True, default=None)

    class Meta:
        model = RecruitmentEmailMessage
        fields = ['id', 'sender', 'subject', 'status', 'error_code', 'application_id', 'analysis_state',
                  'analysis_status', 'analysis_attempts', 'match_score', 'needs_human_review', 'received_at']
        read_only_fields = fields


class GmailConnectSerializer(serializers.Serializer):
    """Connexion d'une boîte Gmail via un authorization code OAuth Google.

    Le frontend doit lancer le consentement Google avec access_type=offline,
    prompt=consent et le scope gmail.readonly, puis poster le code reçu.
    """
    code = serializers.CharField(max_length=2048)
    redirect_uri = serializers.CharField(required=False, allow_blank=True, max_length=255)
    folder = serializers.CharField(default='INBOX', max_length=255)
    default_offer = serializers.PrimaryKeyRelatedField(queryset=JobOffer.objects.none(), required=False, allow_null=True)
    enabled = StrictBooleanField(required=False, default=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context.get('request').user if self.context.get('request') else None
        organization = getattr(user, 'organization', None)
        if organization:
            self.fields['default_offer'].queryset = JobOffer.objects.filter(company=organization)

    def validate_folder(self, value):
        value = value.strip()
        if not value or any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise serializers.ValidationError('Nom de libellé Gmail invalide.')
        return value


class AssignEmailSerializer(serializers.Serializer):
    offer_id = serializers.IntegerField(min_value=1)


class EmailSyncSerializer(serializers.Serializer):
    status = serializers.CharField()
    inbox_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    error_code = serializers.CharField(required=False)
