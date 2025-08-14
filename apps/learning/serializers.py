from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers

from .models import (
    Course, Module, Content, Quiz, QuizQuestion, QuizChoice, QuizAnswer, QuizResult,
    Progress, Certificate, ContentType
)

User = get_user_model()


class CourseProgressSerializer(serializers.Serializer):
    """Serializer pour le progrès d'un cours"""
    course_id = serializers.IntegerField()
    total_contents = serializers.IntegerField()
    completed_contents = serializers.IntegerField()
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    is_completed = serializers.BooleanField()


class UserProgressStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques de progrès utilisateur"""
    total_contents = serializers.IntegerField()
    completed_contents = serializers.IntegerField()
    pending_contents = serializers.IntegerField()
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class QuizStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques de quiz utilisateur"""
    total_attempts = serializers.IntegerField()
    total_quizzes = serializers.IntegerField()
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    best_score = serializers.DecimalField(max_digits=5, decimal_places=2)


class UserProgressInlineSerializer(serializers.Serializer):
    """Serializer inline pour le progrès utilisateur dans les cours"""
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    completed_contents = serializers.IntegerField()
    total_contents = serializers.IntegerField()
    completed_quizzes = serializers.IntegerField()
    total_quizzes = serializers.IntegerField()


class ContentProgressInlineSerializer(serializers.Serializer):
    """Serializer inline pour le progrès d'un contenu spécifique"""
    is_completed = serializers.BooleanField()
    completed_at = serializers.DateTimeField(allow_null=True)


class QuizChoiceSerializer(serializers.ModelSerializer):
    """Serializer pour les choix de réponse des quiz"""

    class Meta:
        model = QuizChoice
        fields = ['id', 'question', 'text', 'is_correct']
        read_only_fields = ['id']

    def validate(self, data):
        """Validation pour s'assurer qu'il y a au moins une réponse correcte par question"""
        if self.instance is None:  # Création
            question = data.get('question')
            if question and data.get('is_correct', False):
                # Vérifier qu'il n'y a pas déjà trop de réponses correctes
                existing_correct = QuizChoice.objects.filter(
                    question=question, is_correct=True
                ).count()
                if existing_correct >= 1 and data.get('is_correct'):
                    # Permettre plusieurs réponses correctes pour les questions à choix multiples
                    pass
        return data


class QuizChoicePublicSerializer(serializers.ModelSerializer):
    """Serializer public pour les choix de réponse des quiz (sans is_correct)"""

    class Meta:
        model = QuizChoice
        fields = ['id', 'text']
        read_only_fields = ['id']


class QuizQuestionSerializer(WritableNestedModelSerializer):
    """Serializer pour les questions de quiz"""
    choices = QuizChoiceSerializer(many=True, required=False)

    class Meta:
        model = QuizQuestion
        fields = ['id', 'quiz', 'title', 'description', 'choices']
        read_only_fields = ['id']

    def validate_choices(self, value):
        """Validation pour s'assurer qu'il y a au moins 2 choix et au moins 1 réponse correcte"""
        if len(value) < 2:
            raise serializers.ValidationError(_("Une question doit avoir au moins 2 choix de réponse"))

        correct_choices = [choice for choice in value if choice.get('is_correct', False)]
        if len(correct_choices) == 0:
            raise serializers.ValidationError(_("Une question doit avoir au moins une réponse correcte"))

        return value


class QuizQuestionPublicSerializer(serializers.ModelSerializer):
    """Serializer public pour les questions de quiz (sans réponses correctes)"""
    choices = QuizChoicePublicSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = ['id', 'title', 'description', 'choices']
        read_only_fields = ['id']


class QuizSerializer(WritableNestedModelSerializer):
    """Serializer pour les quiz"""
    questions = QuizQuestionSerializer(many=True, required=False)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ['id', 'module', 'title', 'description', 'questions', 'question_count']
        read_only_fields = ['id']

    def get_question_count(self, obj: Quiz) -> int:
        return obj.questions.count()

    def validate_questions(self, value):
        """Validation pour s'assurer qu'un quiz a au moins une question"""
        if self.instance is None and len(value) == 0:  # Création
            raise serializers.ValidationError(_("Un quiz doit avoir au moins une question"))
        return value


class QuizPublicSerializer(serializers.ModelSerializer):
    """Serializer public pour les quiz (sans réponses correctes)"""
    questions = QuizQuestionPublicSerializer(many=True, read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ['id', 'module', 'title', 'description', 'questions', 'question_count']
        read_only_fields = ['id']

    def get_question_count(self, obj: Quiz) -> int:
        return obj.questions.count()


class QuizAnswerSerializer(serializers.ModelSerializer):
    """Serializer pour les réponses de quiz"""
    question = QuizQuestionSerializer(read_only=True)
    selected_choices = QuizChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = QuizAnswer
        fields = ['id', 'result', 'question', 'selected_choices', 'is_correct']
        read_only_fields = ['id']


class QuizResultSerializer(serializers.ModelSerializer):
    """Serializer pour les résultats de quiz"""
    user = serializers.StringRelatedField(read_only=True)
    quiz = QuizSerializer(read_only=True)
    answers = QuizAnswerSerializer(many=True, read_only=True)
    quiz_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = QuizResult
        fields = ['id', 'user', 'quiz', 'quiz_id', 'submitted_at', 'score', 'answers']
        read_only_fields = ['id', 'user', 'submitted_at', 'score']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate_quiz_id(self, value):
        """Validation pour vérifier que le quiz existe"""
        try:
            Quiz.objects.get(id=value)
        except Quiz.DoesNotExist:
            raise serializers.ValidationError(_("Le quiz spécifié n'existe pas"))
        return value


class QuizListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des quiz"""
    question_count = serializers.SerializerMethodField()
    is_attempted = serializers.SerializerMethodField()
    is_passed = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ['id', 'module', 'title', 'description', 'question_count', 'is_attempted', 'is_passed', 'best_score']
        read_only_fields = ['id']

    def get_question_count(self, obj: Quiz) -> int:
        return obj.questions.count()

    def get_is_passed(self, obj: Quiz) -> bool:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return QuizResult.objects.filter(
                user=request.user,
                quiz=obj,
                score__gte=70,
            ).exists()
        return False

    def get_is_attempted(self, obj: Quiz) -> bool:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return QuizResult.objects.filter(
                user=request.user,
                quiz=obj,
            ).exists()
        return False

    def get_best_score(self, obj: Quiz) -> float:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            best_result = QuizResult.objects.filter(
                user=request.user,
                quiz=obj,
            ).order_by('-score').first()
            return best_result.score if best_result else 0
        return 0


class ContentDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour les contenus"""
    user_progress = serializers.SerializerMethodField()
    content_url = serializers.SerializerMethodField()

    class Meta:
        model = Content
        fields = ['id', 'module', 'title', 'content_type', 'resource_file', 'resource_url', 'content', 'content_url',
                  'user_progress']
        read_only_fields = ['id']
        extra_kwargs = {
            'resource_file': {'write_only': True},
            'resource_url': {'write_only': True},
        }

    @extend_schema_field(serializers.URLField)
    def get_content_url(self, obj):
        request = self.context.get('request')

        if obj.resource_file:
            url = obj.resource_file.url
            if request:
                return request.build_absolute_uri(url)
            return url
        elif obj.resource_url:
            return obj.resource_url
        return None

    @extend_schema_field(ContentProgressInlineSerializer)
    def get_user_progress(self, obj: Content):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            progress = Progress.objects.filter(user=request.user, content=obj).first()
            if progress:
                return {
                    'is_completed': progress.is_completed,
                    'completed_at': progress.completed_at
                }
        return {'is_completed': False, 'completed_at': None}

    def validate(self, data):
        """Validation basée sur le type de contenu"""
        content_type = data.get('content_type')
        resource_file = data.get('resource_file')
        resource_url = data.get('resource_url')
        content = data.get('content')

        if content_type == ContentType.VIDEO:
            if not resource_file and not resource_url:
                raise serializers.ValidationError({
                    'resource_file': _('Un fichier ou une URL est requis pour le type vidéo.'),
                    'resource_url': _('Un fichier ou une URL est requis pour le type vidéo.')
                })

        elif content_type == ContentType.PDF:
            if not resource_file:
                raise serializers.ValidationError({
                    'resource_file': _('Un fichier PDF est requis pour le type PDF.')
                })

        elif content_type == ContentType.TALK:
            if not resource_url:
                raise serializers.ValidationError({
                    'resource_url': _('Une URL est requise pour le type conférence.')
                })

        elif content_type == ContentType.EXTERNAL_RESOURCE:
            if not resource_url:
                raise serializers.ValidationError({
                    'resource_url': _('Une URL est requise pour le type ressource externe.')
                })

        elif content_type == ContentType.MARKDOWN:
            if not content:
                raise serializers.ValidationError({
                    'content': _('Le contenu markdown est requis pour le type markdown.')
                })

        return data


class ContentListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des contenus"""
    user_progress = serializers.SerializerMethodField()

    class Meta:
        model = Content
        fields = ['id', 'module', 'title', 'content_type', 'user_progress']
        read_only_fields = ['id']

    @extend_schema_field(ContentProgressInlineSerializer)
    def get_user_progress(self, obj: Content):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            progress = Progress.objects.filter(user=request.user, content=obj).first()
            if progress:
                return {
                    'is_completed': progress.is_completed,
                    'completed_at': progress.completed_at
                }
        return {'is_completed': False, 'completed_at': None}


class ModuleSerializer(serializers.ModelSerializer):
    """Serializer pour les modules"""
    contents = ContentListSerializer(many=True, read_only=True)
    quiz = QuizListSerializer(read_only=True)
    content_count = serializers.SerializerMethodField()
    has_quiz = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'description', 'contents', 'quiz', 'content_count', 'has_quiz']
        read_only_fields = ['id']

    def get_content_count(self, obj: Module) -> int:
        return obj.contents.count()

    def get_has_quiz(self, obj: Module) -> bool:
        return hasattr(obj, 'quiz') and obj.quiz is not None

    def validate_title(self, value):
        """Validation pour s'assurer que le titre n'est pas vide"""
        if not value.strip():
            raise serializers.ValidationError(_("Le titre ne peut pas être vide"))
        return value.strip()


class CourseSerializer(WritableNestedModelSerializer):
    """Serializer détaillé pour les cours"""
    modules = ModuleSerializer(many=True, required=False)
    module_count = serializers.SerializerMethodField()
    total_content_count = serializers.SerializerMethodField()
    total_quiz_count = serializers.SerializerMethodField()
    user_progress = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'level', 'is_free',
            'modules', 'module_count', 'total_content_count', 'total_quiz_count', 'user_progress'
        ]
        read_only_fields = ['id']

    def get_module_count(self, obj: Course) -> int:
        return obj.modules.count()

    def get_total_content_count(self, obj: Course) -> int:
        return Content.objects.filter(module__course=obj).count()

    def get_total_quiz_count(self, obj: Course) -> int:
        return Quiz.objects.filter(module__course=obj).count()

    @extend_schema_field(UserProgressInlineSerializer)
    def get_user_progress(self, obj: Course):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            total_contents = Content.objects.filter(module__course=obj).count()
            total_quizzes = Quiz.objects.filter(module__course=obj).count()

            if total_contents == 0 and total_quizzes == 0:
                return {'percentage': 0, 'completed_contents': 0, 'total_contents': 0, 'completed_quizzes': 0,
                        'total_quizzes': 0}

            completed_contents = Progress.objects.filter(
                user=request.user,
                content__module__course=obj,
                is_completed=True
            ).count()

            completed_quizzes = QuizResult.objects.filter(
                user=request.user,
                quiz__module__course=obj,
                score__gte=70,
            ).count()

            total_items = total_contents + total_quizzes
            completed_items = completed_contents + completed_quizzes
            percentage = (completed_items / total_items) * 100 if total_items > 0 else 0

            return {
                'percentage': round(percentage, 2),
                'completed_contents': completed_contents,
                'total_contents': total_contents,
                'completed_quizzes': completed_quizzes,
                'total_quizzes': total_quizzes
            }
        return {'percentage': 0, 'completed_contents': 0, 'total_contents': 0, 'completed_quizzes': 0,
                'total_quizzes': 0}

    def validate_title(self, value):
        """Validation pour s'assurer que le titre n'est pas vide"""
        if not value.strip():
            raise serializers.ValidationError(_("Le titre ne peut pas être vide"))
        return value.strip()


class CourseListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des cours"""
    module_count = serializers.SerializerMethodField()
    total_content_count = serializers.SerializerMethodField()
    total_quiz_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'level', 'is_free', 'module_count', 'total_content_count',
                  'total_quiz_count']
        read_only_fields = ['id']

    def get_module_count(self, obj: Course) -> int:
        return obj.modules.count()

    def get_total_content_count(self, obj: Course) -> int:
        return Content.objects.filter(module__course=obj).count()

    def get_total_quiz_count(self, obj: Course) -> int:
        return Quiz.objects.filter(module__course=obj).count()


class ProgressSerializer(serializers.ModelSerializer):
    """Serializer pour les progrès"""
    user = serializers.StringRelatedField(read_only=True)
    content = ContentListSerializer(read_only=True)
    content_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Progress
        fields = ['id', 'user', 'content', 'content_id', 'is_completed', 'completed_at']
        read_only_fields = ['id', 'user', 'completed_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate_content_id(self, value):
        """Validation pour vérifier que le contenu existe"""
        try:
            Content.objects.get(id=value)
        except Content.DoesNotExist:
            raise serializers.ValidationError(_("Le contenu spécifié n'existe pas"))
        return value


class CertificateSerializer(serializers.ModelSerializer):
    """Serializer pour les certificats"""
    user = serializers.StringRelatedField(read_only=True)
    course = CourseListSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Certificate
        fields = ['id', 'user', 'course', 'course_id', 'issued_at', 'file']
        read_only_fields = ['id', 'user', 'issued_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate_course_id(self, value):
        """Validation pour vérifier que le cours existe"""
        try:
            Course.objects.get(id=value)
        except Course.DoesNotExist:
            raise serializers.ValidationError(_("Le cours spécifié n'existe pas"))
        return value


class QuizSubmissionChoiceSerializer(serializers.Serializer):
    """Serializer pour les choix sélectionnés dans une soumission de quiz"""
    question_id = serializers.IntegerField()
    choice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )

    def validate_question_id(self, value):
        """Validation pour vérifier que la question existe"""
        try:
            QuizQuestion.objects.get(id=value)
        except QuizQuestion.DoesNotExist:
            raise serializers.ValidationError(_("La question spécifiée n'existe pas"))
        return value

    def validate_choice_ids(self, value):
        """Validation pour vérifier que tous les choix existent"""
        if not value:
            raise serializers.ValidationError(_("Au moins un choix doit être sélectionné"))

        existing_choices = QuizChoice.objects.filter(id__in=value).count()
        if existing_choices != len(value):
            raise serializers.ValidationError(_("Un ou plusieurs choix spécifiés n'existent pas"))

        return value


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer pour soumettre un quiz complet"""
    answers = QuizSubmissionChoiceSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError(_("Au moins une réponse est requise"))

        # Vérifier que toutes les questions du quiz ont une réponse
        question_ids = [answer['question_id'] for answer in value]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError(_("Chaque question ne peut avoir qu'une seule réponse"))

        return value


class QuizAnswerSubmissionSerializer(serializers.Serializer):
    """Serializer pour soumettre une réponse à un quiz (compatible avec les views existantes)"""
    answers = QuizSubmissionChoiceSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError(_("Au moins une réponse est requise"))
        return value
