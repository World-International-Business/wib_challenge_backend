from django.db import transaction
from drf_spectacular.utils import inline_serializer
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

    def validate_status(self, value):
        if value != Question.Status.PENDING and value != '':
            raise serializers.ValidationError('Status must be PENDING or empty')
        return value

    @transaction.atomic
    def create(self, validated_data):
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        return instance


EvaluationQuestionProportions = inline_serializer(
    'EvaluationQuestionProportions',
    fields={
        Question.Difficulty.EASY: serializers.IntegerField(),
        Question.Difficulty.MEDIUM: serializers.IntegerField(),
        Question.Difficulty.HARD: serializers.IntegerField(),
    }
)

TechnologyStats = inline_serializer(
    'TechnologyStats',
    fields={
        'id': serializers.IntegerField(),
        'name': serializers.CharField(),
        'url': serializers.URLField(),
        'question_count': serializers.IntegerField(),
        'available': EvaluationQuestionProportions
    }
)
