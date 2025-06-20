from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import OrgEvaluation, ExperienceLevel, OrgQuestion, OrgChoice, EvaluationInvitation
from organizations.permissions import IsOrganization
from organizations.serializers import EvaluationInvitationSerializer, InviteCandidateSerializer, OrgQuestionSerializer, OrgSubmissionAttemptDetailSerializer
from organizations.serializers.evaluations import EvaluationResponseSerializer, AutomaticEvaluationSerializer, \
    ProportionEvaluationSerializer
from organizations.serializers.results import CandidateResultSerializer
from questions.models import Question
from wib_challenge.permissions import ReadOnly

EXPERIENCE_QUOTAS = {
    ExperienceLevel.JUNIOR: {
        Question.Difficulty.EASY: 60,  # 60% facile
        Question.Difficulty.MEDIUM: 30,  # 30% intermédiaire
        Question.Difficulty.HARD: 10,  # 10% difficile
    },
    ExperienceLevel.INTERMEDIATE: {
        Question.Difficulty.EASY: 30,  # 30% facile
        Question.Difficulty.MEDIUM: 50,  # 50% intermédiaire
        Question.Difficulty.HARD: 20,  # 20% difficile
    },
    ExperienceLevel.SENIOR: {
        Question.Difficulty.EASY: 15,  # 15% facile
        Question.Difficulty.MEDIUM: 35,  # 35% intermédiaire
        Question.Difficulty.HARD: 50,  # 50% difficile
    }
}

QUESTIONS_PER_TECH = {
    ExperienceLevel.JUNIOR: 10,  # 10 questions par technologie
    ExperienceLevel.INTERMEDIATE: 15,  # 15 questions par technologie
    ExperienceLevel.SENIOR: 20  # 20 questions par technologie
}


class OrgEvaluationViewSet(viewsets.ModelViewSet):
    serializer_class = EvaluationResponseSerializer
    permission_classes = [IsAuthenticated, IsOrganization | ReadOnly]
    queryset = OrgEvaluation.objects.all()

    def get_queryset(self):
        if hasattr(self.request.user, 'organization'):
            return super().get_queryset().filter(organization=self.request.user.organization)
        elif self.request.user.is_superuser:
            return super().get_queryset()
        return OrgEvaluation.objects.none()

    def perform_create(self, serializer):
        if hasattr(self.request.user, 'organization'):
            return serializer.save(organization=self.request.user.organization)
        else:
            raise ValidationError(
                _("Only organizations can create evaluations."))

    def check_can_update(self, evaluation: OrgEvaluation):
        if OrgEvaluation.objects.filter(
            id=evaluation.id, attempts__started_at__isnull=False,
        ).exists():
            raise ValidationError(
                _("Cette évaluation ne peut pas être modifiée."))

    @extend_schema(
        request=InviteCandidateSerializer
    )
    @action(detail=True, methods=['post'], url_path='invite-candidates')
    @transaction.atomic
    def invite_candidates(self, request, pk=None, organization_pk=None):
        """Crée une invitation pour un candidat"""
        evaluation = self.get_object()
        candidates = request.data.get('candidates', [])
        expires_at = request.data.get('expires_at')

        for candidate in candidates:
            serializer = EvaluationInvitationSerializer(
                data={**candidate, 'expires_at': expires_at}, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save(evaluation=evaluation)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=ProportionEvaluationSerializer,
        responses={200: EvaluationResponseSerializer},
        summary="Mise à jour par proportions personnalisées",
        description="Ajoute ou remplace des questions selon des proportions personnalisées par technologie et difficulté",
    )
    @transaction.atomic
    @action(detail=True, methods=['put', 'post'], url_path='add-question-basic', url_name='add-question-basic')
    def update_by_proportion(self, request, pk=None, organization_pk=None):
        """
        Mise à jour d'une évaluation avec des proportions personnalisées
        Format attendu :
        {
            "proportions" : [
                {
                    "technology": 1,
                    "easy": 3,
                    "medium": 8,
                    "hard": 7
                },
                {...}
            ],
            "replace_existing" : true/false
        }
        """
        evaluation = self.get_object()
        self.check_can_update(evaluation)

        serializer = ProportionEvaluationSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        proportions = serializer.validated_data['proportions']
        replace_existing = serializer.validated_data['replace_existing']

        if replace_existing:
            evaluation.questions.all().delete()
        else:
            evaluation.questions.filter(technology__isnull=False).delete()

        for prop in proportions:
            technology = prop['technology']
            num_easy = prop.get('easy', 0)
            num_medium = prop.get('medium', 0)
            num_hard = prop.get('hard', 0)

            if num_easy > 0:
                easy_questions = Question.objects.filter(
                    technology=technology,
                    difficulty=Question.Difficulty.EASY,
                    status=Question.Status.PUBLISHED
                ).order_by('?')[:num_easy]

                self._add_questions_to_evaluation(evaluation, easy_questions)

            if num_medium > 0:
                medium_questions = Question.objects.filter(
                    technology=technology,
                    difficulty=Question.Difficulty.MEDIUM,
                    status=Question.Status.PUBLISHED
                ).order_by('?')[:num_medium]

                self._add_questions_to_evaluation(evaluation, medium_questions)

            if num_hard > 0:
                hard_questions = Question.objects.filter(
                    technology=technology,
                    difficulty=Question.Difficulty.HARD,
                    status=Question.Status.PUBLISHED
                ).order_by('?')[:num_hard]

                self._add_questions_to_evaluation(evaluation, hard_questions)

        evaluation.refresh_from_db()
        response_data = self.get_serializer(evaluation).data
        return Response(response_data)

    @extend_schema(
        request=OrgQuestionSerializer,
        responses={201: OrgQuestionSerializer},
        summary="Ajout manuel de questions",
        description="Ajoute une question soit en utilisant une question existante, soit en créant une nouvelle",
    )
    @action(detail=True, methods=['put', 'post'], url_path='add-question', url_name='add-question')
    def add_from_scratch(self, request, pk=None):
        """
        Ajout manuel de questions à une évaluation:
        - Soit en créant de nouvelles questions
        - Soit en ajoutant des questions existantes
        """
        evaluation = self.get_object()
        self.check_can_update(evaluation)
        serializer = OrgQuestionSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        serializer.save(evaluation=evaluation)
        serializer_data = self.get_serializer(evaluation).data
        return Response(serializer_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={200: CandidateResultSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None, organization_pk=None):
        """Récupère les résultats d'une évaluation"""
        evaluation = self.get_object()
        invitations = EvaluationInvitation.objects.filter(
            evaluation=evaluation).all()

        page = self.paginate_queryset(invitations)
        if page is not None:
            serializer = CandidateResultSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CandidateResultSerializer(invitations, many=True)
        return Response(serializer.data)

    @staticmethod
    def _add_questions_to_evaluation(evaluation: OrgEvaluation, questions: QuerySet[Question]):
        """Helper pour ajouter des questions à l'évaluation"""
        questions = questions.prefetch_related('choices')
        existing_original_ids = set(
            evaluation.questions.filter(original_question__in=questions.values_list('id', flat=True)).values_list(
                'original_question_id',
                flat=True
            )
        )
        new_questions = [
            q for q in questions if q.id not in existing_original_ids]

        bulk_create_org_question(new_questions, evaluation)

    @extend_schema(
        responses={200: OrgSubmissionAttemptDetailSerializer}
    )
    @action(detail=True, methods=['get'], url_path='results/(?P<invitation_pk>[0-9]+)')
    def candidate_results(self, request, pk=None, invitation_pk=None, organization_pk=None):
        """
        Récupère les résultats d'une évaluation pour un candidat spécifique
        """
        evaluation = self.get_object()

        try:
            invitation = EvaluationInvitation.objects.get(
                pk=invitation_pk, evaluation=evaluation)
            candidate = invitation.candidate
        except EvaluationInvitation.DoesNotExist:
            return Response({"detail": _("Invitation non trouvée.")}, status=status.HTTP_404_NOT_FOUND)

        if not candidate:
            return Response({"detail": _("Candidat non trouvé.")}, status=status.HTTP_404_NOT_FOUND)

        attempt = evaluation.attempts.filter(candidate=candidate).first()
        if not attempt or not attempt.is_completed:
            return Response({"detail": _("Aucune tentative trouvée pour ce candidat.")}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrgSubmissionAttemptDetailSerializer(
            attempt, context={'request': request})
        return Response(serializer.data)


@extend_schema(
    request=AutomaticEvaluationSerializer,
    summary="Création automatique d'évaluation",
    description="Génère une évaluation basée sur une profession, un niveau d'expérience et des technologies",
    responses={201: EvaluationResponseSerializer}
)
@permission_classes([IsAuthenticated, IsOrganization])
@api_view(['POST'])
@transaction.atomic
def generate_evaluation(request):
    """
    Création automatique d'une évaluation basée sur :
    * Profession (pour le titre)
    * Niveau d'expérience (junior, intermediate, senior)
    * Liste de Technologies
    """
    serializer = AutomaticEvaluationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    profession = serializer.validated_data['profession']
    experience_level = serializer.validated_data['experience_level']
    technologies = serializer.validated_data['technologies']

    evaluation = OrgEvaluation.objects.create(
        organization=request.user.organization,
        title=f"Évaluation {profession.title} - {experience_level.capitalize()}",
        description=f"Évaluation automatique pour {profession.title} niveau {experience_level.capitalize()}",
        questions_order=OrgEvaluation.QuestionOrder.SKILL
    )

    quotas = EXPERIENCE_QUOTAS[experience_level]
    questions_per_tech = QUESTIONS_PER_TECH[experience_level]

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

        all_questions = []
        for questions in questions_by_difficulty.values():
            all_questions.extend(questions)
        bulk_create_org_question(all_questions, evaluation)

    response_data = EvaluationResponseSerializer(evaluation, context={
        'request': request,
    }).data
    return Response(response_data, status=status.HTTP_201_CREATED)


@transaction.atomic
def bulk_create_org_question(questions: list[Question], evaluation: OrgEvaluation):
    org_questions = [
        OrgQuestion(
            evaluation=evaluation,
            original_question=question,
            text=question.text,
            explanation=question.explanation,
            difficulty=question.difficulty,
            duration=question.duration,
            technology=question.technology
        ) for question in questions
    ]
    created_questions = OrgQuestion.objects.bulk_create(org_questions)

    org_choices = []
    for i, question in enumerate(questions):
        org_question = created_questions[i]
        for choice in question.choices.all():
            org_choices.append(OrgChoice(
                question=org_question,
                text=choice.text,
                is_correct=choice.is_correct
            ))
    if org_choices:
        OrgChoice.objects.bulk_create(org_choices)
