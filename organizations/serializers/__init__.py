from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import inline_serializer, extend_schema_field
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from core.serializers import TechnologySerializer
from organizations.models import (
    Organization, OrgEvaluation, OrgQuestion, OrgChoice,
    OrgSubmissionAttempt, OrgAnswer, OrgSubmission, Candidate, EvaluationInvitation
)
from organizations.utils import send_invitation_email
from questions.models import Question


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ['id', 'email', 'full_name', 'created_at', 'organization']
        read_only_fields = ['id', 'created_at', 'organization']


class OrgChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgChoice
        fields = ['id', 'text', 'is_correct']
        read_only_fields = ['id', 'question']


class OrgQuestionSerializer(serializers.ModelSerializer):
    choices = OrgChoiceSerializer(many=True, required=False)
    original_question = serializers.PrimaryKeyRelatedField(
        write_only=True, queryset=Question.objects.filter(status=Question.Status.PUBLISHED), required=False
    )
    technology = TechnologySerializer(read_only=True)

    class Meta:
        model = OrgQuestion
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at',
                            'id', 'technology', 'evaluation']

    @transaction.atomic
    def create(self, validated_data):
        original_question = validated_data.pop('original_question', None)
        choices_data = validated_data.pop('choices', [])

        if original_question:
            question = OrgQuestion.objects.create(
                original_question=original_question,
                text=original_question.text,
                explanation=original_question.explanation,
                difficulty=original_question.difficulty,
                duration=original_question.duration,
                technology=original_question.technology,
                **validated_data
            )
            OrgChoice.objects.bulk_create([
                OrgChoice(question=question, text=choice.text,
                          is_correct=choice.is_correct)
                for choice in original_question.choices.all()
            ])
        else:
            question = OrgQuestion.objects.create(**validated_data)
            OrgChoice.objects.bulk_create([
                OrgChoice(question=question, **choice_data) for choice_data in choices_data
            ])
        return question

    def update(self, instance, validated_data):
        choices_data = validated_data.pop('choices', [])
        validated_data.pop('original_question', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        OrgChoice.objects.filter(question=instance).delete()
        OrgChoice.objects.bulk_create([
            OrgChoice(question=instance, **choice_data) for choice_data in choices_data
        ])
        return instance


class OrgEvaluationSerializer(WritableNestedModelSerializer):
    questions = OrgQuestionSerializer(many=True, read_only=True)
    questions_count = serializers.SerializerMethodField()
    estimated_time = serializers.SerializerMethodField()

    class Meta:
        model = OrgEvaluation
        fields = [
            'id', 'title', 'description', 'questions_order', 'estimated_time',
            'slug', 'questions', 'questions_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_questions_count(self, obj) -> int:
        return obj.questions.count()

    def get_estimated_time(self, obj: OrgEvaluation) -> float:
        """Retourne l'estimation du temps nécessaire pour compléter l'évaluation"""
        aggregate = obj.questions.filter(status=Question.Status.PUBLISHED).order_by('?')[:20].aggregate(
            total_time=Sum('duration'))
        return aggregate['total_time'] or 0


class OrgSubmissionAttemptSerializer(serializers.ModelSerializer):
    candidate = CandidateSerializer(read_only=True)

    questions = serializers.SerializerMethodField()

    class Meta:
        model = OrgSubmissionAttempt
        fields = '__all__'
        read_only_fields = [f.name for f in OrgSubmissionAttempt._meta.fields]

    def _select_questions(self, evaluation: OrgEvaluation):
        """Sélectionne les questions selon l'ordre configuré"""
        questions = evaluation.questions.all()
        if evaluation.questions_order == OrgEvaluation.QuestionOrder.ADDED:
            return questions.order_by('created_at')
        elif evaluation.questions_order == OrgEvaluation.QuestionOrder.SKILL:
            return questions.order_by('technology', 'difficulty')
        else:
            return questions.order_by('?')

    @extend_schema_field(
        OrgQuestionSerializer(many=True)
    )
    @transaction.atomic
    def get_questions(self, obj):
        evaluation = obj.evaluation
        questions = self._select_questions(evaluation)
        questions = questions.exclude(
            answers__attempt__candidate=self.instance.candidate)
        return OrgQuestionSerializer(questions, many=True).data


class OrgAnswerSerializer(serializers.ModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(
        many=True, queryset=OrgChoice.objects.all())

    class Meta:
        model = OrgAnswer
        fields = ['id', 'question', 'selected_choices', 'delta_time', 'status']
        read_only_fields = ['id']


class OrgSubmissionSerializer(serializers.ModelSerializer):
    answers = OrgAnswerSerializer(
        source='attempt.answers', many=True, read_only=True)

    class Meta:
        model = OrgSubmission
        fields = ['id', 'score', 'submitted_at', 'answers']
        read_only_fields = ['id', 'score', 'submitted_at']


InviteCandidateSerializer = inline_serializer(
    'InviteCandidateSerializer',
    fields={
        'expires_at': serializers.DateField(),
        'candidates': CandidateSerializer(many=True)
    }
)


class EvaluationInvitationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    full_name = serializers.CharField(write_only=True)

    class Meta:
        model = EvaluationInvitation
        fields = ['id', 'email', 'full_name',
                  'evaluation', 'status', 'expires_at']
        read_only_fields = ['id', 'status', 'evaluation']

    def validate_expire_at(self, value):
        if timezone.now() > value:
            raise serializers.ValidationError(
                "La date d'expiration doit être dans le futur.")
        return value

    def create(self, validated_data):
        email = validated_data.pop('email', '')
        full_name = validated_data.pop('full_name', '')
        expire_at = validated_data.pop('expires_at', None)
        evaluation = validated_data.get('evaluation')
        organization = evaluation.organization

        candidate = Candidate.objects.create(
            email=email,
            organization=organization,
            full_name=full_name
        )

        existing_invitation = EvaluationInvitation.objects.filter(
            candidate=candidate,
            evaluation=evaluation,
            status=EvaluationInvitation.Status.PENDING,
            expires_at__gt=timezone.now()
        ).first()

        if existing_invitation:
            return existing_invitation

        invitation = EvaluationInvitation.objects.create(
            candidate=candidate,
            evaluation=evaluation,
            expires_at=expire_at
        )

        send_invitation_email(self.context['request'], invitation)
        return invitation
