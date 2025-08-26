from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsCreator
from apps.evaluations.models import Evaluation, QuestionOrder, ExperienceLevel, EvaluationType
from apps.evaluations.serializers.evaluations import AutomaticEvaluationSerializer, EvaluationResponseSerializer, \
    AutomaticPersonalityEvaluationSerializer
from apps.questions.models import Question, Choice
from services.generate_evaluation import generate_evaluation

EXPERIENCE_QUOTAS = {
    ExperienceLevel.JUNIOR: {
        Question.Difficulty.EASY: 60,
        Question.Difficulty.MEDIUM: 30,
        Question.Difficulty.HARD: 10,
    },
    ExperienceLevel.INTERMEDIATE: {
        Question.Difficulty.EASY: 30,
        Question.Difficulty.MEDIUM: 50,
        Question.Difficulty.HARD: 20,
    },
    ExperienceLevel.SENIOR: {
        Question.Difficulty.EASY: 15,
        Question.Difficulty.MEDIUM: 35,
        Question.Difficulty.HARD: 50,
    }
}

QUESTIONS_PER_TECH = {
    ExperienceLevel.JUNIOR: 10,
    ExperienceLevel.INTERMEDIATE: 15,
    ExperienceLevel.SENIOR: 20
}


class GenerateEvaluationFromSpecsView(GenericAPIView):
    """
    Création automatique d'une évaluation basée sur :
    * Profession (pour le titre)
    * Niveau d'expérience (junior, intermediate, senior)
    * Liste de Technologies
    """
    permission_classes = [IsAuthenticated, IsCreator]
    serializer_class = AutomaticEvaluationSerializer

    @extend_schema(
        summary="Création automatique d'évaluation",
        description="Génère une évaluation basée sur une profession, un niveau d'expérience et des technologies",
        responses={201: EvaluationResponseSerializer}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profession = serializer.validated_data['profession']
        experience_level = serializer.validated_data['experience_level']
        technologies = serializer.validated_data['technologies']

        evaluation = create_evaluation_from_techs(
            publisher=request.user,
            title=f"Évaluation {profession.title} - {experience_level.capitalize()}",
            description=f"Évaluation automatique pour {profession.title} niveau {experience_level.capitalize()}",
            experience_level=experience_level,
            technologies=technologies
        )

        response_data = EvaluationResponseSerializer(evaluation, context={
            'request': request,
        }).data
        return Response(response_data, status=status.HTTP_201_CREATED)


def create_evaluation_from_techs(publisher, title, description, experience_level, technologies):
    evaluation = Evaluation.objects.create(
        publisher=publisher,
        title=title,
        description=description,
        questions_order=QuestionOrder.SKILL
    )
    quotas = EXPERIENCE_QUOTAS[experience_level]
    questions_per_tech = QUESTIONS_PER_TECH[experience_level]
    all_questions = []
    for technology in technologies:
        num_easy = int(questions_per_tech *
                       quotas[Question.Difficulty.EASY] / 100)
        num_medium = int(questions_per_tech *
                         quotas[Question.Difficulty.MEDIUM] / 100)
        num_hard = int(questions_per_tech *
                       quotas[Question.Difficulty.HARD] / 100)

        total = num_easy + num_medium + num_hard
        if total < questions_per_tech:
            num_medium += questions_per_tech - total

        difficulties_counts = {
            Question.Difficulty.EASY: num_easy,
            Question.Difficulty.MEDIUM: num_medium,
            Question.Difficulty.HARD: num_hard
        }

        questions_by_difficulty = {}
        for difficulty, count in difficulties_counts.items():
            if count > 0:
                questions_by_difficulty[difficulty] = list(Question.objects.filter(
                    technology=technology,
                    difficulty=difficulty,
                    status=Question.Status.PUBLISHED
                ).order_by('?').prefetch_related('choices')[:count])

        for questions in questions_by_difficulty.values():
            all_questions.extend(questions)
    if all_questions:
        evaluation.questions.set(all_questions)
    return evaluation


class GeneratePersonalityEvaluationView(GenericAPIView):
    """
    Création automatique d'une évaluation de personnalité basée sur :
    * Profession (pour le titre)
    * Niveau d'expérience (junior, intermediate, senior)
    * Description du poste
    """
    permission_classes = [IsAuthenticated, IsCreator]
    serializer_class = AutomaticPersonalityEvaluationSerializer

    @extend_schema(
        summary="Création automatique d'évaluation de personnalité",
        description="Génère une évaluation de personnalité basée sur une profession, un niveau d'expérience et d'une description",
        responses={201: EvaluationResponseSerializer}
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profession = serializer.validated_data['profession']
        experience_level = serializer.validated_data['experience_level']
        description = serializer.validated_data['description']

        try:
            data = generate_evaluation(profession, experience_level, description)
        except Exception as e:
            return Response(
                {"detail": f"Erreur lors de la génération des questions: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        evaluation = Evaluation.objects.create(
            publisher=request.user,
            title=f"Évaluation Personnalité {profession.title} - {experience_level.capitalize()}",
            description=data.theme,
            profession=profession,
            type=EvaluationType.PERSONALITY,
            questions_order=QuestionOrder.RANDOM
        )

        all_questions = [
            Question(
                text=question.text,
                evaluation=evaluation,
                duration=60,
                difficulty=Question.Difficulty.MEDIUM,
            )
            for question in data.questions
        ]
        Question.objects.bulk_create(all_questions)
        Choice.objects.bulk_create([
            Choice(
                question=question,
                text=choice.text,
                is_correct=choice.is_correct,
            )
            for i, question in enumerate(all_questions) for choice in data.questions[i].choices
        ])

        response_data = EvaluationResponseSerializer(evaluation, context={
            'request': request,
        }).data
        return Response(
            response_data, status=status.HTTP_201_CREATED
        )
