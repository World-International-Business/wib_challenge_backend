from django.db.models import Sum
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from accounts.serializers import PublisherSerializer
from core.serializers import TechnologySerializer, ProfessionSerializer
from evaluations.models import Evaluation, SubmissionAttempt, Answer, Submission, Competition, EvaluationType
from questions.models import Choice, Question
from questions.serializers import QuestionSerializer


class CompetitionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = '__all__'

    def get_is_active(self, obj):
        """Vérifie si la compétition est active"""
        from django.utils import timezone
        now = timezone.now()
        return (obj.started_at is None or obj.started_at <= now) and (obj.ended_at is None or obj.ended_at > now)


class EvaluationSerializer(serializers.ModelSerializer):
    estimated_time = serializers.SerializerMethodField()
    is_under_construction = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    publisher = PublisherSerializer(read_only=True)
    technology = TechnologySerializer(read_only=True)
    profession = ProfessionSerializer(read_only=True)
    technology_id = serializers.PrimaryKeyRelatedField(
        queryset=TechnologySerializer.Meta.model.objects.all(), source='technology', write_only=True
    )
    profession_id = serializers.PrimaryKeyRelatedField(
        queryset=ProfessionSerializer.Meta.model.objects.all(), source='profession', write_only=True
    )
    questions_count = serializers.SerializerMethodField()
    competition = CompetitionSerializer(required=False)

    class Meta:
        model = Evaluation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'slug']

    def create(self, validated_data):
        competition = validated_data.pop('competition', None)
        evaluation = super().create(validated_data)
        if competition:
            evaluation.competition = Competition.objects.create(evaluation=evaluation, **competition)
            evaluation.evaluation_type = EvaluationType.COMPETITION
        else:
            evaluation.evaluation_type = EvaluationType.NORMAL
        evaluation.save()
        return evaluation

    def update(self, instance, validated_data):
        competition = validated_data.pop('competition', None)
        evaluation = super().update(instance, validated_data)
        if competition:
            evaluation.competition = Competition.objects.update_or_create(evaluation=evaluation, defaults=competition)[
                0]
            evaluation.evaluation_type = EvaluationType.COMPETITION
        else:
            evaluation.evaluation_type = EvaluationType.NORMAL
        evaluation.save()
        return evaluation

    def get_estimated_time(self, obj: Evaluation) -> float:
        """Retourne l'estimation du temps nécessaire pour compléter l'évaluation"""
        aggregate = obj.questions.filter(status=Question.Status.PUBLISHED).order_by('?')[:20].aggregate(
            total_time=Sum('duration'))
        return aggregate['total_time'] or 0

    def get_is_under_construction(self, obj: Evaluation) -> bool:
        """Retourne True si l'évaluation est en construction"""
        return not obj.is_constructed

    def get_questions_count(self, obj: Evaluation) -> int:
        """Retourne le nombre de questions publiées"""
        return obj.questions.count()

    def get_image(self, obj: Evaluation) -> str | None:
        request = self.context.get('request', None)
        image = obj.image or (obj.technology.image if obj.technology else None)

        if image and request:
            return request.build_absolute_uri(image.url)
        elif image:
            return image.url
        return None


class AnswerSerializer(WritableNestedModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Choice.objects)
    question_id = serializers.PrimaryKeyRelatedField(
        write_only=True, queryset=Question.objects, source='question')
    question = QuestionSerializer(read_only=True)

    class Meta:
        model = Answer
        fields = '__all__'
        read_only_fields = ['attempt', 'is_correct', 'answered_at', 'score']

    def validate_status(self, value):
        """Valide que le statut est dans la liste des statuts autorisés"""
        valid_statuses = [Answer.Status.DISCARDED, Answer.Status.TIMEOUT]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f'Status must be one of {", ".join(valid_statuses)}')
        return value


class SubmissionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(
        many=True, read_only=True, source='attempt.answers')
    candidate = serializers.PrimaryKeyRelatedField(
        read_only=True, source='attempt.candidate')
    evaluation = serializers.PrimaryKeyRelatedField(
        read_only=True, source='attempt.evaluation')
    started_at = serializers.DateTimeField(
        read_only=True, source='attempt.started_at')
    ended_at = serializers.DateTimeField(
        read_only=True, source='attempt.ended_at')
    correct_answers_count = serializers.SerializerMethodField()
    incorrect_answers_count = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = '__all__'

    def get_correct_answers_count(self, obj) -> int:
        """Retourne le nombre de réponses correctes"""
        return obj.attempt.answers.filter(is_correct=True).count()

    def get_incorrect_answers_count(self, obj) -> int:
        """Retourne le nombre de réponses incorrectes"""
        return obj.attempt.answers.filter(is_correct=False).count()


class SubmissionAttemptSerializer(serializers.ModelSerializer):
    submission = SubmissionSerializer(read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    answers_count = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionAttempt
        fields = '__all__'

    def get_answers_count(self, obj) -> int:
        """Retourne le nombre de réponses données"""
        return obj.answers.count()
