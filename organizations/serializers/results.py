from datetime import datetime

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, inline_serializer

from core.models import Technology
from evaluations.models import Answer
from organizations.models import EvaluationInvitation, OrgSubmissionAttempt


class CandidateResultSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True, source='candidate.email')
    full_name = serializers.CharField(read_only=True, source='candidate.full_name')
    stats = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationInvitation
        fields = ['id', 'email', 'full_name', 'evaluation', 'status', 'expires_at', 'invited_at', 'stats', 'last_activity']
        read_only_fields = ['id', 'status', 'evaluation']

    def attempt(self, instance: EvaluationInvitation) -> OrgSubmissionAttempt | None:
        return instance.evaluation.attempts.filter(candidate=instance.candidate).first()

    def get_last_activity(self, obj: EvaluationInvitation) -> datetime:
        attempt = self.attempt(obj)
        if obj.status == EvaluationInvitation.Status.ACCEPTED:
            if attempt.is_completed:
                return attempt.ended_at
            return attempt.started_at
        else:
            return obj.invited_at

    @extend_schema_field(
        inline_serializer(
            name='CandidateResultStats',
            many=True,
            fields={
                'technology': serializers.CharField(),
                'score': serializers.FloatField(),
                'total_questions': serializers.IntegerField(),
                'correct_answers': serializers.IntegerField(),
                'incorrect_answers': serializers.IntegerField(),
                'partial_answers': serializers.IntegerField(),
            },
        )
    )
    def get_stats(self, obj: EvaluationInvitation):
        attempt = self.attempt(obj)
        if not attempt or not attempt.is_completed:
            return None
        technologies = Technology.objects.filter(org_questions__evaluation=obj.evaluation).distinct()
        
        stats = []
        for tech in technologies:
            # Get questions related to this technology in the evaluation
            tech_questions = tech.org_questions.filter(evaluation=obj.evaluation)
            # Get answers for these questions in the attempt
            answers = attempt.answers.filter(question__in=tech_questions)
            
            total_questions = tech_questions.count()
            correct_answers = answers.filter(status=Answer.Status.CORRECT).count()
            partial_answers = answers.filter(status=Answer.Status.PARTIAL).count()
            incorrect_answers = answers.filter(status=Answer.Status.INCORRECT).count()
            
            score = attempt.submission.score or 0.0
            
            stats.append({
                'technology': tech.name,
                'score': round(score, 2),
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'incorrect_answers': incorrect_answers,
                'partial_answers': partial_answers,
            })
            
        return stats
