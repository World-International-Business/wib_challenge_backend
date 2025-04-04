import random

from django.db.models import Sum
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from core.models import Technology
from core.serializers import TechnologySerializer
from evaluations.models import Evaluation


class EvaluationSerializer(serializers.ModelSerializer):
    estimated_time = serializers.SerializerMethodField()
    technologies = serializers.SerializerMethodField()
    technologies_ids = serializers.PrimaryKeyRelatedField(many=True, write_only=True, queryset=Technology.objects)

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
        aggregate = questions[:20].aggregate(estimated_time=Sum('duration'))
        return aggregate['estimated_time'] or 0

    @extend_schema_field(
        inline_serializer(
            name='EvaluationTechnologies',
            fields={
                'name': serializers.CharField(),
                'image': serializers.URLField(),
            }
        )
    )
    def get_technologies(self, obj: Evaluation) -> list:
        return [
            {
                'name': technology.name,
                'image': self.context['request'].build_absolute_uri(technology.image.url),
            }
            for technology in obj.technologies.all()
        ]

    def create(self, validated_data):
        technologies = validated_data.pop('technologies_ids')
        evaluation = Evaluation.objects.create(**validated_data)
        evaluation.technologies.add(*technologies)
        return evaluation

    def update(self, instance, validated_data):
        technologies = validated_data.pop('technologies_ids')
        instance = super().update(instance, validated_data)
        instance.technologies.clear()
        instance.technologies.add(*technologies)
        return instance
