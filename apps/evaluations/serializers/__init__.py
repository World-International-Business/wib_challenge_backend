from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import inline_serializer, extend_schema_field
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from apps.accounts.serializers import PublisherSerializer
from apps.core.serializers import TechnologySerializer, ProfessionSerializer
from apps.evaluations.models import Evaluation, SubmissionAttempt, Answer, Competition, EvaluationType, \
    Candidate, Participant, EvaluationInvitation, QuestionOrder, SkillEvaluation
from apps.evaluations.utils import send_invitation_email
from apps.questions.models import Choice, Question
from apps.questions.serializers import QuestionSerializer


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = '__all__'
        extra_kwargs = {'owner': {'write_only': True, 'required': False}}


class ParticipantSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    real_id = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = ['id', 'email', 'full_name', 'type', 'created_at', 'real_id']

    def get_email(self, obj) -> str:
        return obj.email

    def get_full_name(self, obj) -> str:
        return obj.full_name

    def get_real_id(self, obj) -> int:
        return obj.real_id


class CompetitionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = '__all__'

    def get_is_active(self, obj) -> bool:
        """Vérifie si la compétition est active"""
        from django.utils import timezone
        now = timezone.now()
        return (obj.started_at is None or obj.started_at <= now) and (obj.ended_at is None or obj.ended_at > now)


class EvaluationSerializer(WritableNestedModelSerializer):
    estimated_time = serializers.SerializerMethodField()
    is_under_construction = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    publisher = PublisherSerializer(read_only=True)
    technology = TechnologySerializer(read_only=True)
    profession = ProfessionSerializer(read_only=True)
    technology_id = serializers.PrimaryKeyRelatedField(queryset=TechnologySerializer.Meta.model.objects.all(),
                                                       source='technology', write_only=True, required=False)
    profession_id = serializers.PrimaryKeyRelatedField(queryset=ProfessionSerializer.Meta.model.objects.all(),
                                                       source='profession', write_only=True, required=False)
    questions_count = serializers.SerializerMethodField()
    max_score = serializers.SerializerMethodField()
    is_public = serializers.SerializerMethodField()
    is_organizational = serializers.SerializerMethodField()
    experienceLevel = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    competition = CompetitionSerializer(required=False)

    class Meta:
        model = Evaluation
        exclude = ['questions']
        read_only_fields = ['id', 'created_at', 'updated_at', 'slug']

    def validate_evaluation_type(self, value):
        if value == EvaluationType.COMPETITION and not self.context['request'].user.is_staff:
            raise serializers.ValidationError('Un utilisateur non admin ne peut pas créer une compétition')
        return value

    def create(self, validated_data):
        competition = validated_data.pop('competition', None)
        evaluation = super().create(validated_data)
        if competition:
            evaluation.competition = Competition.objects.create(evaluation=evaluation, **competition)
            evaluation.evaluation_type = EvaluationType.COMPETITION
        evaluation.save()
        return evaluation

    def update(self, instance, validated_data):
        competition = validated_data.pop('competition', None)
        evaluation = super().update(instance, validated_data)
        if competition:
            evaluation.competition = Competition.objects.update_or_create(evaluation=evaluation, defaults=competition)[
                0]
            evaluation.evaluation_type = EvaluationType.COMPETITION
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
        return obj.questions.filter(status=Question.Status.PUBLISHED).count()

    def get_max_score(self, obj: Evaluation) -> int:
        """Retourne le score maximum possible"""
        return obj.max_score

    def get_is_public(self, obj: Evaluation) -> bool:
        """Retourne True si l'évaluation est publique"""
        return not hasattr(obj.publisher, 'organization')

    def get_is_organizational(self, obj: Evaluation) -> bool:
        """Retourne True si l'évaluation appartient à une organisation"""
        return hasattr(obj.publisher, 'organization')

    def get_image(self, obj: Evaluation) -> str | None:
        request = self.context.get('request', None)
        image = obj.image or (obj.technology.image if obj.technology else None)

        if image and request:
            return request.build_absolute_uri(image.url)
        elif image:
            return image.url
        return None

    def get_experienceLevel(self, obj: Evaluation) -> str:
        """Mapper difficulty vers experienceLevel pour le frontend"""
        difficulty_to_experience = {
            Evaluation.Difficulty.BEGINNER: 'junior',
            Evaluation.Difficulty.INTERMEDIATE: 'intermediate',
            Evaluation.Difficulty.EXPERT: 'senior'
        }
        return difficulty_to_experience.get(obj.difficulty, 'junior')

    def get_status(self, obj: Evaluation) -> str:
        """Retourne le statut de l'évaluation : draft, active ou archived"""
        if obj.archived:
            return 'archived'
        
        # Une évaluation est active si le champ is_active est True
        if obj.is_active:
            return 'active'
        else:
            return 'draft'


class SkillEvaluationSerializer(serializers.ModelSerializer):
    evaluation = EvaluationSerializer(read_only=True)

    class Meta:
        model = SkillEvaluation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']


class AnswerSerializer(WritableNestedModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(many=True, queryset=Choice.objects)
    question_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=Question.objects, source='question')
    question = QuestionSerializer(read_only=True)

    class Meta:
        model = Answer
        fields = '__all__'
        read_only_fields = ['attempt', 'is_correct', 'answered_at', 'score']

    def validate_status(self, value):
        """Valide que le statut est dans la liste des statuts autorisés"""
        valid_statuses = [Answer.Status.DISCARDED, Answer.Status.TIMEOUT]
        if value not in valid_statuses:
            raise serializers.ValidationError(f'Status must be one of {", ".join(valid_statuses)}')
        return value


class SubmissionAttemptListSerializer(serializers.ModelSerializer):
    candidate = ParticipantSerializer(source='participant', read_only=True)
    title = serializers.CharField(source='evaluation.title', read_only=True)
    score = serializers.FloatField(source='submission.score', read_only=True)

    class Meta:
        model = SubmissionAttempt
        fields = '__all__'
        read_only_fields = [f.name for f in SubmissionAttempt._meta.fields]


class SubmissionAttemptSerializer(serializers.ModelSerializer):
    candidate = ParticipantSerializer(source='participant', read_only=True)
    questions = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionAttempt
        fields = '__all__'
        read_only_fields = [f.name for f in SubmissionAttempt._meta.fields]

    def _select_questions(self, evaluation: Evaluation):
        """Sélectionne les questions selon l'ordre configuré"""
        questions = evaluation.questions.all()
        if evaluation.questions_order == QuestionOrder.ADDED:
            return questions.order_by('created_at')
        elif evaluation.questions_order == QuestionOrder.SKILL:
            return questions.order_by('technology', 'difficulty')
        else:
            return questions.order_by('?')

    @extend_schema_field(QuestionSerializer(many=True))
    @transaction.atomic
    def get_questions(self, obj: SubmissionAttempt):
        evaluation = obj.evaluation
        has_questions = obj.questions.exists()
        if has_questions:
            questions = obj.questions.all()
        else:
            questions = self._select_questions(evaluation)
        questions = questions.exclude(answers__attempt__participant=obj.participant, answers__attempt=obj)
        questions = questions[:20] if obj.evaluation.publisher.is_admin else questions
        if not has_questions:
            obj.questions.set(questions)
        return QuestionSerializer(questions, many=True).data


class ParticipantCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un participant candidat"""
    candidate_email = serializers.EmailField(write_only=True)
    candidate_name = serializers.CharField(max_length=255, write_only=True)

    class Meta:
        model = Participant
        fields = ['id', 'type', 'candidate_email', 'candidate_name']
        read_only_fields = ['id']

    def validate_type(self, value):
        """Valide que seul le type CANDIDATE peut être créé"""
        if value != Participant.Type.CANDIDATE:
            raise serializers.ValidationError("Seuls les participants candidats peuvent être créés via cette API")
        return value

    def create(self, validated_data):
        candidate_email = validated_data.pop('candidate_email')
        candidate_name = validated_data.pop('candidate_name')

        candidate, created = Candidate.objects.get_or_create(
            email=candidate_email,
            owner=self.context['request'].user,
            defaults={'full_name': candidate_name}
        )

        participant, created = Participant.objects.get_or_create(
            candidate=candidate,
            defaults={'type': Participant.Type.CANDIDATE}
        )

        return participant


class EvaluationInvitationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    full_name = serializers.CharField(write_only=True)

    class Meta:
        model = EvaluationInvitation
        fields = ['id', 'email', 'full_name',
                  'evaluation', 'status', 'expires_at']
        read_only_fields = ['id', 'status', 'evaluation']

    def validate_expires_at(self, value):
        if timezone.now() > value:
            raise serializers.ValidationError(
                "La date d'expiration doit être dans le futur.")
        return value

    def create(self, validated_data):
        email = validated_data.pop('email', '')
        full_name = validated_data.pop('full_name', '')
        expire_at = validated_data.pop('expires_at', None)
        evaluation = validated_data.get('evaluation')

        candidate, _ = Candidate.objects.get_or_create(
            email=email,
            owner=evaluation.publisher,
            defaults={'full_name': full_name},
        )

        invitation, _ = EvaluationInvitation.objects.update_or_create(
            candidate=candidate,
            evaluation=evaluation,
            defaults={'expires_at': expire_at},
        )

        participant, _ = Participant.objects.get_or_create(
            candidate=candidate,
            defaults={'type': Participant.Type.CANDIDATE},
        )
        SubmissionAttempt.objects.get_or_create(
            participant=participant,
            evaluation=evaluation,
        )

        send_invitation_email(self.context['request'], invitation)
        return invitation


InviteCandidateSerializer = inline_serializer(
    'InviteCandidateSerializer',
    fields={
        'expires_at': serializers.DateField(),
        'candidates': CandidateSerializer(many=True)
    }
)
