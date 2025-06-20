from datetime import datetime

from django.db.models import Sum
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, inline_serializer

from core.models import Technology
from evaluations.models import Answer
from organizations.models import EvaluationInvitation, OrgSubmissionAttempt


class CandidateResultSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True, source='candidate.email')
    full_name = serializers.CharField(
        read_only=True, source='candidate.full_name')
    score = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    other_stats = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationInvitation
        fields = ['id', 'score', 'email', 'full_name', 'evaluation', 'status',
                  'expires_at', 'invited_at', 'stats', 'other_stats', 'last_activity']
        read_only_fields = ['id', 'status', 'evaluation']

    def attempt(self, instance: EvaluationInvitation) -> OrgSubmissionAttempt | None:
        return instance.evaluation.attempts.filter(candidate=instance.candidate).first()

    def get_score(self, obj: EvaluationInvitation) -> float:
        attempt = self.attempt(obj)
        if not attempt or not attempt.is_completed or not attempt.submission:
            return 0.0
        return round(attempt.submission.score, 2)

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
                'timeout_answers': serializers.IntegerField(),
                'discarded_answers': serializers.IntegerField(),
            },
        )
    )
    def get_stats(self, obj: EvaluationInvitation):
        attempt = self.attempt(obj)
        if not attempt or not attempt.is_completed:
            return None
        technologies = Technology.objects.filter(
            org_questions__evaluation=obj.evaluation).distinct()

        stats = []
        for tech in technologies:
            # Get questions related to this technology in the evaluation
            tech_questions = tech.org_questions.filter(
                evaluation=obj.evaluation)
            # Get answers for these questions in the attempt
            answers = attempt.answers.filter(question__in=tech_questions)

            total_questions = tech_questions.count()
            correct_answers = answers.filter(
                status=Answer.Status.CORRECT).count()
            partial_answers = answers.filter(
                status=Answer.Status.PARTIAL).count()
            incorrect_answers = answers.filter(
                status=Answer.Status.INCORRECT).count()
            timeout_answers = answers.filter(
                status=Answer.Status.TIMEOUT).count()
            discarded_answers = answers.filter(
                status=Answer.Status.DISCARDED).count()

            score = score = answers.aggregate(total_score=Sum('score'))[
                'total_score'] or 0.0

            stats.append({
                'technology': tech.name,
                'score': round(score, 2),
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'incorrect_answers': incorrect_answers,
                'partial_answers': partial_answers,
                'timeout_answers': timeout_answers,
                'discarded_answers': discarded_answers,
            })

        return stats

    @extend_schema_field(
        inline_serializer(
            name='CandidateResultOtherStats',
            fields={
                'score': serializers.FloatField(),
                'total_questions': serializers.IntegerField(),
                'correct_answers': serializers.IntegerField(),
                'incorrect_answers': serializers.IntegerField(),
                'timeout_answers': serializers.IntegerField(),
                'discarded_answers': serializers.IntegerField(),
                'partial_answers': serializers.IntegerField(),
            }
        )
    )
    def get_other_stats(self, obj: EvaluationInvitation):
        attempt = self.attempt(obj)
        if not attempt or not attempt.is_completed:
            return None

        total_questions = attempt.questions.filter(technology=None).count()
        if total_questions == 0:
            return None
        answers = attempt.answers.filter(question__technology=None)

        correct_answers = answers.filter(status=Answer.Status.CORRECT).count()
        partial_answers = answers.filter(status=Answer.Status.PARTIAL).count()
        timeout_answers = answers.filter(
            status=Answer.Status.TIMEOUT).count()
        discarded_answers = answers.filter(
            status=Answer.Status.DISCARDED).count()
        incorrect_answers = answers.filter(
            status=Answer.Status.INCORRECT).count()

        score = answers.aggregate(total_score=Sum('score'))[
            'total_score'] or 0.0

        return {
            'score': round(score, 2),
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'timeout_answers': timeout_answers,
            'discarded_answers': discarded_answers,
            'partial_answers': partial_answers,
        }
