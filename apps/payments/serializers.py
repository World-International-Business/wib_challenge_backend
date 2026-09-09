from rest_framework import serializers

from .models import Payment


class CourseCheckoutSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=True)
    provider = serializers.ChoiceField(choices=Payment.Provider.choices, required=True)
    return_url = serializers.URLField(required=True)
    cancel_url = serializers.URLField(required=True)


class PaymentSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Payment
        fields = ['payment_id', 'user', 'purpose', 'course', 'certificate', 'amount', 'currency',
                  'provider', 'provider_reference', 'status', 'failure_reason', 'metadata',
                  'paid_at', 'checkout_url', 'created_at', 'updated_at']
        read_only_fields = fields
