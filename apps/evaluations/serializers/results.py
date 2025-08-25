from datetime import datetime

from django.db.models import Sum
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from apps.core.models import Technology
from apps.evaluations.models import Answer, EvaluationInvitation, SubmissionAttempt, Submission
from apps.evaluations.serializers import AnswerSerializer, ParticipantSerializer


class SubmissionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(
        source='attempt.answers', many=True, read_only=True)
    max_score = serializers.FloatField(
        source='attempt.evaluation.max_score', read_only=True)

    class Meta:
        model = Submission
        fields = ['id', 'score', 'submitted_at', 'answers', 'max_score', 'personality_detail']
        read_only_fields = ['id', 'score', 'submitted_at', 'personality_detail']


class SubmissionAttemptDetailSerializer(serializers.ModelSerializer):
    candidate = ParticipantSerializer(read_only=True, source='participant')
    submission = SubmissionSerializer(read_only=True)

    class Meta:
        model = SubmissionAttempt
        exclude = ['questions', 'participant']
        read_only_fields = [f.name for f in SubmissionAttempt._meta.fields]


class CandidateResultSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True, source='participant.email')
    full_name = serializers.CharField(read_only=True, source='participant.full_name')
    score = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    other_stats = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()
    invitation = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionAttempt
        fields = '__all__'
        read_only_fields = ['id', 'evaluation']

    def get_score(self, obj: SubmissionAttempt) -> float:
        if not obj.is_completed or not obj.submission:
            return 0.0
        return round(obj.submission.score, 2)

    def get_last_activity(self, obj: SubmissionAttempt) -> datetime:
        if obj.is_completed:
            return obj.ended_at
        elif obj.started_at:
            return obj.started_at
        else:
            invitation = EvaluationInvitation.objects.filter(
                evaluation=obj.evaluation, candidate=obj.participant.candidate
            ).first()

            if invitation:
                return invitation.invited_at
            else:
                return obj.evaluation.created_at

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
    def get_stats(self, attempt: SubmissionAttempt):
        if not attempt or not attempt.is_completed:
            return None
        technologies = Technology.objects.filter(questions__evaluations=attempt.evaluation).distinct()

        stats = []
        for tech in technologies:
            tech_questions = tech.questions.filter(
                evaluations=attempt.evaluation)
            answers = attempt.answers.filter(question__in=tech_questions)

            total_questions = tech_questions.count()
            correct_answers, discarded_answers, incorrect_answers, partial_answers, timeout_answers = self.split_answers(
                answers)

            score = answers.aggregate(total_score=Sum('score'))[
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
    def get_other_stats(self, attempt: SubmissionAttempt):
        if not attempt or not attempt.is_completed:
            return None

        total_questions = attempt.questions.filter(technology=None).count()
        if total_questions == 0:
            return None
        answers = attempt.answers.filter(question__technology=None)

        correct_answers, discarded_answers, incorrect_answers, partial_answers, timeout_answers = self.split_answers(
            answers)

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

    def split_answers(self, answers):
        correct_answers = answers.filter(status=Answer.Status.CORRECT).count()
        partial_answers = answers.filter(status=Answer.Status.PARTIAL).count()
        timeout_answers = answers.filter(
            status=Answer.Status.TIMEOUT).count()
        discarded_answers = answers.filter(
            status=Answer.Status.DISCARDED).count()
        incorrect_answers = answers.filter(
            status=Answer.Status.INCORRECT).count()
        return correct_answers, discarded_answers, incorrect_answers, partial_answers, timeout_answers

    @extend_schema_field(
        inline_serializer(
            name='CandidateResultInvitation',
            fields={
                'id': serializers.IntegerField(),
                'token': serializers.CharField(),
                'status': serializers.CharField(),
                'invited_at': serializers.DateTimeField(),
                'expires_at': serializers.DateTimeField(),
            }
        )
    )
    def get_invitation(self, obj: SubmissionAttempt):
        invitation = EvaluationInvitation.objects.filter(
            evaluation=obj.evaluation, candidate=obj.participant.candidate
        ).first()
        if invitation:
            return {
                'id': invitation.id,
                'token': invitation.token,
                'status': invitation.status,
                'invited_at': invitation.invited_at,
                'expires_at': invitation.expires_at,
            }
        return None
