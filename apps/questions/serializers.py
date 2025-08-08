from django.db import transaction
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from apps.accounts.serializers import PublisherSerializer
from apps.core.serializers import TechnologySerializer
from apps.questions.models import Question, Choice


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'is_correct', 'question']
        extra_kwargs = {
            'question': {'read_only': True},
        }


class QuestionSerializer(WritableNestedModelSerializer):
    choices = ChoiceSerializer(many=True)
    publisher = PublisherSerializer(read_only=True)
    # profession = serializers.SlugRelatedField(
    #     slug_field='title', read_only=True, source='evaluation.profession')
    technology = TechnologySerializer(read_only=True)
    weight = serializers.IntegerField(read_only=True)

    class Meta:
        model = Question
        fields = '__all__'
        read_only_fields = ['publisher', 'status', 'technology']

    @transaction.atomic
    def create(self, validated_data):
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.status = Question.Status.PENDING
        return instance
