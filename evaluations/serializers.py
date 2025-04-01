import random

from django.db.models import Sum
from rest_framework import serializers

from evaluations.models import Evaluation


class EvaluationSerializer(serializers.ModelSerializer):
    estimated_time = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'slug']

    def get_estimated_time(self, obj: Evaluation) -> float:
        questions = obj.questions.all()
        if obj.questions_order == Evaluation.QuestionOrder.RANDOM:
            ids = list(questions.values_list('id', flat=True)[:20])
            questions = questions.filter(id__in=random.sample(ids, len(questions)))
        elif obj.questions_order == Evaluation.QuestionOrder.TECHNO:
            questions = questions.order_by('technology__name')
        elif obj.questions_order == Evaluation.QuestionOrder.ADDED:
            questions = questions.order_by('-created_at')
        return float(questions[:20].aggregate(total_time=Sum('duration'))['total_time'])
