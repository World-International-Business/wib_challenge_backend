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


class AddQuestionSerializer(serializers.Serializer):
    question = serializers.IntegerField()

    def validate(self, attrs):
        question_id = attrs.get('question')
        if Question.objects.filter(pk=question_id).exists():
            return attrs
        raise serializers.ValidationError('Question does not exist')


class QuestionSerializer(WritableNestedModelSerializer):
    choices = ChoiceSerializer(many=True)
    publisher = PublisherSerializer(read_only=True)
    technology = TechnologySerializer(read_only=True)
    weight = serializers.IntegerField(read_only=True)

    class Meta:
        model = Question
        fields = '__all__'
        read_only_fields = ['publisher', 'technology']

    def validate_status(self, value):
        if value != Question.Status.PENDING and value != '':
            raise serializers.ValidationError('Status must be PENDING or empty')
        return value


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
