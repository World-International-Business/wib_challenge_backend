from rest_framework import serializers
from django.db.models import Count
from core.models import Profession, Technology

class _QuestionStatsSerializerMixin(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()
    
    def get_questions_count(self, obj) -> int:
        if not hasattr(obj, 'questions'):
            return obj.__class__.objects.filter(id=obj.id).aggregate(questions_count=Count('technologies__questions'))['questions_count'] or 0
        return obj.questions.count()

class TechnologySerializer(_QuestionStatsSerializerMixin):
    class Meta:
        model = Technology
        fields = '__all__'

class ProfessionSerializer(_QuestionStatsSerializerMixin):
    technologies = TechnologySerializer(many=True, read_only=True)

    class Meta:
        model = Profession
        fields = '__all__'