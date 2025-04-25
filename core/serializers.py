from functools import lru_cache

from django.db.models import Count
from rest_framework import serializers

from core.models import Profession, Technology


class _QuestionStatsSerializerMixin(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()

    @lru_cache(maxsize=4)
    def get_questions_count(self, obj) -> int:
        if not hasattr(obj, 'questions'):
            return obj.__class__.objects.filter(id=obj.id).annotate(
                count=Count('technologies__questions')
            ).values_list('count', flat=True).first() or 0
        return obj.questions.count()


class TechnologySerializer(_QuestionStatsSerializerMixin):
    class Meta:
        model = Technology
        fields = '__all__'


class ProfessionSerializer(_QuestionStatsSerializerMixin):
    class Meta:
        model = Profession
        exclude = ('technologies',)


class ProfessionDetailSerializer(ProfessionSerializer):
    technologies = TechnologySerializer(many=True, read_only=True)

    class Meta:
        model = Profession
        fields = '__all__'
