from django.db.models import Sum
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from core.models import Profession
from core.models import Technology
from organizations.models import OrgEvaluation, ExperienceLevel
from questions.models import Question


class AutomaticEvaluationSerializer(serializers.Serializer):
    """Sérialiseur pour la création automatique d'évaluation basée sur le niveau d'expérience et les technologies"""
    profession = serializers.SlugRelatedField(required=True, help_text="Profession cible (ex: 'Développeur Frontend')",
                                              slug_field='title',
                                              queryset=Profession.objects.all())
    experience_level = serializers.ChoiceField(
        choices=ExperienceLevel.choices,
        default=ExperienceLevel.JUNIOR,
        help_text="Niveau d'expérience du candidat"
    )
    technologies = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Technology.objects.all(),
        help_text="Liste des IDs des technologies à inclure dans l'évaluation"
    )


class ProportionItemSerializer(serializers.Serializer):
    """Sérialiseur pour une proportion de technologie dans une évaluation"""
    technology = serializers.PrimaryKeyRelatedField(
        queryset=Technology.objects.all(),
        help_text="ID de la technologie"
    )
    easy = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
        help_text="Nombre de questions faciles"
    )
    medium = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
        help_text="Nombre de questions de difficulté moyenne"
    )
    hard = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
        help_text="Nombre de questions difficiles"
    )


class ProportionEvaluationSerializer(serializers.Serializer):
    """Sérialiseur pour la mise à jour d'une évaluation par proportions personnalisées"""
    proportions = ProportionItemSerializer(many=True, required=True)
    replace_existing = serializers.BooleanField(
        default=False,
        help_text="Si true, remplace toutes les questions existantes. Si false, ajoute aux questions existantes."
    )


EvaluationQuestionProportions = inline_serializer(
    'EvaluationQuestionProportions',
    fields={
        Question.Difficulty.EASY: serializers.IntegerField(),
        Question.Difficulty.MEDIUM: serializers.IntegerField(),
        Question.Difficulty.HARD: serializers.IntegerField(),
    }
)


class EvaluationResponseSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la réponse après manipulation d'une évaluation"""

    questions = serializers.SerializerMethodField()
    candidates_count = serializers.SerializerMethodField()
    others_count = serializers.SerializerMethodField()
    score = serializers.FloatField(source='submission.score', read_only=True)

    class Meta:
        model = OrgEvaluation
        fields = '__all__'
        read_only_fields = ['organization', 'slug']

    def get_candidates_count(self, obj: OrgEvaluation) -> int:
        """Retourne le nombre de candidats ayant été invités à l'évaluation"""
        return obj.invitations.count()

    @extend_schema_field(
        inline_serializer(
            'EvaluationQuestionStatsPerTech',
            many=True,
            fields={
                'id': serializers.IntegerField(),
                'name': serializers.CharField(),
                'url': serializers.URLField(),
                'question_count': serializers.IntegerField(),
                'estimated_time': serializers.IntegerField(),
                'proportions': EvaluationQuestionProportions,
                'available': EvaluationQuestionProportions
            }
        )
    )
    def get_questions(self, obj):
        technologies = Technology.objects.filter(
            org_questions__evaluation=obj).distinct()

        result = []
        for tech in technologies:
            questions_in_eval = obj.questions.filter(technology=tech)
            nb_questions = questions_in_eval.count()

            proportions = {
                Question.Difficulty.EASY: questions_in_eval.filter(difficulty=Question.Difficulty.EASY).count(),
                Question.Difficulty.MEDIUM: questions_in_eval.filter(difficulty=Question.Difficulty.MEDIUM).count(),
                Question.Difficulty.HARD: questions_in_eval.filter(
                    difficulty=Question.Difficulty.HARD).count()
            }

            available_questions = Question.objects.filter(
                technology=tech,
                status=Question.Status.PUBLISHED
            )

            available = {
                Question.Difficulty.EASY: available_questions.filter(difficulty=Question.Difficulty.EASY).count(),
                Question.Difficulty.MEDIUM: available_questions.filter(difficulty=Question.Difficulty.MEDIUM).count(),
                Question.Difficulty.HARD: available_questions.filter(
                    difficulty=Question.Difficulty.HARD).count()
            }

            estimated_time = questions_in_eval.aggregate(total_duration=Sum('duration'))[
                'total_duration'] or 0

            result.append({
                'id': tech.id,
                'name': tech.name,
                'url': self.context['request'].build_absolute_uri(tech.image.url) if tech.image else None,
                'question_count': nb_questions,
                'proportions': proportions,
                'available': available,
                'estimated_time': estimated_time
            })

        return result

    def get_others_count(self, obj: OrgEvaluation) -> int:
        return obj.questions.filter(technology=None).count()


TechnologyStats = inline_serializer(
    'TechnologyStats',
    fields={
        'id': serializers.IntegerField(),
        'name': serializers.CharField(),
        'url': serializers.URLField(),
        'question_count': serializers.IntegerField(),
        'available': EvaluationQuestionProportions
    }
)
