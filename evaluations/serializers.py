import random

from django.db.models import Sum
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from evaluations.models import Evaluation, SubmissionAttempt, Answer, Submission
from questions.models import Choice, Question


class EvaluationSerializer(serializers.ModelSerializer):
    estimated_time = serializers.SerializerMethodField()
    is_under_construction = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'slug']
        depth = 1

    def get_estimated_time(self, obj: Evaluation) -> float:
        questions = obj.questions.all()
        ids = list(questions.values_list('id', flat=True)[:20])
        questions = questions.filter(id__in=random.sample(ids, len(questions)))
        aggregate = questions[:20].aggregate(estimated_time=Sum('duration'))
        return aggregate['estimated_time'] or 0

    def get_is_under_construction(self, obj: Evaluation) -> bool:
        """
        Return True if the evaluation is under construction
        """
        return obj.questions.filter(status=Question.Status.PUBLISHED).count() < 20


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = '__all__'


class SubmissionAttemptSerializer(serializers.ModelSerializer):
    submission = SubmissionSerializer(read_only=True)

    class Meta:
        model = SubmissionAttempt
        fields = '__all__'


class AnswerSerializer(WritableNestedModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(many=True, write_only=True, queryset=Choice.objects)

    class Meta:
        model = Answer
        fields = '__all__'
        read_only_fields = ['attempt', 'is_correct', 'answered_at']
