from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers

from .models import (
    Course, Module, Content, Quiz, QuizQuestion, QuizChoice, QuizAnswer, QuizResult,
    Progress, Certificate
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


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses d'erreur"""
    detail = serializers.CharField()


class SuccessMessageSerializer(serializers.Serializer):
    """Serializer pour les messages de succès"""
    detail = serializers.CharField()


class QuizChoiceSerializer(serializers.ModelSerializer):
    """Serializer pour les choix de réponse des quiz"""

    class Meta:
        model = QuizChoice
        fields = ['id', 'question', 'text', 'is_correct']
        read_only_fields = ['id']


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
        fields = ['id', 'quiz', 'title', 'description', 'explanation', 'choices']
        read_only_fields = ['id']


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


class QuizListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des quiz"""
    question_count = serializers.SerializerMethodField()
    is_attempted = serializers.SerializerMethodField()
    is_passed = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ['id', 'module', 'title', 'description', 'question_count', 'is_attempted', 'is_passed']
        read_only_fields = ['id']

    def get_question_count(self, obj: Quiz) -> int:
        return obj.questions.count()

    def get_is_passed(self, obj: Quiz) -> bool:
        return QuizResult.objects.filter(
            user=self.context['request'].user,
            quiz=obj,
            score__gte=70,
        ).exists()

    def get_is_attempted(self, obj: Quiz) -> bool:
        return QuizResult.objects.filter(
            user=self.context['request'].user,
            quiz=obj,
        ).exists()


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
        return None


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
        return None


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
            if total_contents == 0:
                return {'percentage': 0, 'completed_contents': 0, 'total_contents': 0}

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

            percentage = ((completed_contents + completed_quizzes) / (total_contents + total_quizzes)) * 100
            return {
                'percentage': round(percentage, 2),
                'completed_contents': completed_contents,
                'total_contents': total_contents,
                'completed_quizzes': completed_quizzes,
                'total_quizzes': total_quizzes
            }
        return None


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


class QuizSubmissionChoiceSerializer(serializers.Serializer):
    """Serializer pour les choix sélectionnés dans une soumission de quiz"""
    question_id = serializers.IntegerField()
    choice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer pour soumettre un quiz complet"""
    answers = QuizSubmissionChoiceSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError(_("Au moins une réponse est requise"))
        return value


class QuizAnswerSubmissionSerializer(serializers.Serializer):
    """Serializer pour soumettre une réponse à un quiz (compatible avec les views existantes)"""
    answers = QuizSubmissionChoiceSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError(_("Au moins une réponse est requise"))
        return value
