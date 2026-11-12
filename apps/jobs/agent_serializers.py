from rest_framework import serializers

from apps.jobs.models import AgentEvent, ComplianceConsent, ComplianceRequest, RetentionPolicy, OfferConversation, ConversationMessage


class AgentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentEvent
        fields = ['id', 'timestamp', 'action', 'actor', 'target_id', 'input_data', 'model_version', 'human_validator']
        read_only_fields = fields


class ReviewRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceConsent
        fields = ['id', 'user', 'organization', 'purpose', 'granted', 'updated_at']
        read_only_fields = fields


class ConsentUpdateSerializer(serializers.Serializer):
    organization = serializers.IntegerField(min_value=1)
    purpose = serializers.ChoiceField(choices=['talent_pool', 'interview_recording', 'interview_transcription'])
    granted = serializers.BooleanField()


class PrivacyRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceRequest
        fields = ['id', 'organization', 'kind', 'status', 'created_at']
        read_only_fields = fields


class OrganizationInputSerializer(serializers.Serializer):
    organization = serializers.IntegerField(min_value=1)


class RetentionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetentionPolicy
        fields = ['candidate_days', 'talent_pool_days', 'updated_at', 'updated_by']
        read_only_fields = ['updated_at', 'updated_by']
        extra_kwargs = {
            'candidate_days': {'min_value': 1, 'max_value': 3650},
            'talent_pool_days': {'min_value': 1, 'max_value': 3650},
        }


class SlotInputSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class BookingCreateSerializer(serializers.Serializer):
    slots = SlotInputSerializer(many=True, allow_empty=False, max_length=30)


class SlotSelectionSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(min_value=1)


class OnboardingStepSerializer(serializers.Serializer):
    id = serializers.SlugField(max_length=60)
    title = serializers.CharField(max_length=200)
    status = serializers.ChoiceField(choices=['pending', 'in_progress', 'completed', 'blocked', 'not_applicable'])
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class OnboardingObjectiveSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    status = serializers.ChoiceField(choices=['pending', 'in_progress', 'completed', 'blocked'])


class OnboardingObjectivesSerializer(serializers.Serializer):
    day30 = OnboardingObjectiveSerializer(many=True, required=False, max_length=50)
    day60 = OnboardingObjectiveSerializer(many=True, required=False, max_length=50)
    day90 = OnboardingObjectiveSerializer(many=True, required=False, max_length=50)


class AdministrativeDeclarationSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['identity_document', 'work_permit', 'bank_details', 'tax_registration', 'social_security'])
    status = serializers.ChoiceField(choices=['missing', 'declared_received'])
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class OnboardingUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=0)
    start_date = serializers.DateField(required=False, allow_null=True)
    steps = OnboardingStepSerializer(many=True, required=False, allow_empty=False, max_length=30)
    objectives = OnboardingObjectivesSerializer(required=False)
    administrative_documents = AdministrativeDeclarationSerializer(many=True, required=False, max_length=20)

    def validate(self, attrs):
        if len(attrs) == 1:
            raise serializers.ValidationError('Au moins un champ du plan doit être fourni.')
        for field, key in [('steps', 'id'), ('administrative_documents', 'kind')]:
            values = [item[key] for item in attrs.get(field, [])]
            if len(values) != len(set(values)):
                raise serializers.ValidationError({field: 'Les identifiants doivent être uniques.'})
        return attrs


class OnboardingResponseSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    eligible = serializers.BooleanField()
    initialized = serializers.BooleanField()
    start_date = serializers.DateField(allow_null=True)
    steps = OnboardingStepSerializer(many=True)
    objectives = OnboardingObjectivesSerializer()
    administrative_documents = serializers.ListField(child=serializers.DictField())
    version = serializers.IntegerField()
    updated_at = serializers.DateTimeField(allow_null=True)
    updated_by = serializers.IntegerField(allow_null=True)


class OTPInputSerializer(serializers.Serializer):
    code = serializers.RegexField(r'^\d{6}$')


class ReviewResponseSerializer(serializers.Serializer):
    needs_human_review = serializers.BooleanField()
    review_reason = serializers.CharField(required=False)


class DashboardStatsSerializer(serializers.Serializer):
    total_applications = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    needs_human_review = serializers.IntegerField()
    accepted_conversion_rate = serializers.FloatField(allow_null=True)
    average_days_to_signed_contract = serializers.FloatField(allow_null=True)
    signed_contracts = serializers.IntegerField()


class PublicSlotSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class PublicSlotsSerializer(serializers.Serializer):
    slots = PublicSlotSerializer(many=True)
    booked = serializers.BooleanField()
    expires_at = serializers.DateTimeField()


class BookingCreatedSerializer(serializers.Serializer):
    token = serializers.CharField()
    expires_at = serializers.DateTimeField()
    booking_id = serializers.IntegerField()


class BookedSerializer(serializers.Serializer):
    booked = serializers.BooleanField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class OTPSentSerializer(serializers.Serializer):
    status = serializers.CharField()
    expires_in = serializers.IntegerField()


class OTPVerifiedSerializer(serializers.Serializer):
    verified = serializers.BooleanField()


class RetentionResponseSerializer(serializers.Serializer):
    candidate_days = serializers.IntegerField(allow_null=True)
    talent_pool_days = serializers.IntegerField(allow_null=True)
    configured = serializers.BooleanField()
    updated_at = serializers.DateTimeField(required=False)
    updated_by = serializers.IntegerField(required=False, allow_null=True)


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ['id', 'role', 'content', 'blocks', 'created_at']
        read_only_fields = fields


class OfferConversationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferConversation
        fields = ['id', 'title', 'state', 'job_offer', 'created_at', 'updated_at']
        read_only_fields = fields


class OfferConversationDetailSerializer(serializers.ModelSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = OfferConversation
        fields = ['id', 'title', 'state', 'draft', 'job_offer', 'messages', 'created_at', 'updated_at']
        read_only_fields = fields


class ConversationMessageInputSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=20000, allow_blank=False)


class AssistantMessageResponseSerializer(serializers.Serializer):
    message = ConversationMessageSerializer()
    state = serializers.ChoiceField(choices=OfferConversation.State.choices)


class ChannelStatusSerializer(serializers.Serializer):
    name = serializers.CharField()
    state = serializers.ChoiceField(choices=['queued', 'publishing', 'published', 'failed'])
    url = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class PublishResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    channels = ChannelStatusSerializer(many=True)
