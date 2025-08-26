from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied, NotAuthenticated
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.evaluations.models import (
    EvaluationInvitation, SubmissionAttempt, Answer, Submission, Evaluation, Participant
)
from apps.evaluations.serializers import SubmissionAttemptSerializer, AnswerSerializer
from apps.evaluations.serializers.results import SubmissionSerializer, SubmissionAttemptDetailSerializer
from services.corrector import correct_submission


@dataclass
class Invitation:
    participant: Participant
    evaluation: Evaluation
    current: EvaluationInvitation | None


@extend_schema(tags=['Sessions d\'évaluations'])
class CandidateEvaluationViewSet(viewsets.GenericViewSet):
    """Vue pour les candidats qui passent une évaluation avec un token d'invitation"""

    def get_serializer_class(self):
        if self.action == 'submit_answer':
            return AnswerSerializer
        elif self.action == 'finish':
            return SubmissionSerializer
        elif self.action == 'start_session':
            return SubmissionAttemptSerializer
        return None

    @staticmethod
    def verify_invitation(request):
        """Vérifie si l'invitation est valide"""
        payload = str(request.GET.get('payload', ''))

        if not payload or payload == '':
            raise ValidationError(_('Vous devez fournir un token d\'invitation ou id d\'evaluation'))

        if not payload.isnumeric():
            invitation = get_object_or_404(
                EvaluationInvitation.objects.select_related(
                    'evaluation', 'candidate'),
                token=payload
            )

            if invitation.status not in (EvaluationInvitation.Status.PENDING, EvaluationInvitation.Status.ACCEPTED):
                raise PermissionDenied(
                    _("Cette invitation n'est plus valide (status: {})").format(invitation.status))

            if timezone.now() > invitation.expires_at:
                invitation.status = EvaluationInvitation.Status.EXPIRED
                invitation.save()
                raise PermissionDenied(_("Cette invitation a expiré"))

            return Invitation(
                evaluation=invitation.evaluation,
                participant=Participant.objects.get_or_create(
                    candidate=invitation.candidate, defaults={'type': Participant.Type.CANDIDATE}
                )[0],
                current=invitation
            )
        else:
            if request.user.is_authenticated and request.user.is_dev:
                evaluation = get_object_or_404(Evaluation, pk=int(payload))
                return Invitation(
                    evaluation=evaluation,
                    participant=Participant.objects.get_or_create(
                        user=request.user, defaults={'type': Participant.Type.USER}
                    )[0],
                    current=None
                )
            raise NotAuthenticated(_("Vous devez être connecté pour accéder à cette ressource"))

    def verify_attempt(self, request, attempt_id=None, ended=False):
        """Vérifie si la tentative existe et appartient au candidat associé au token"""
        invitation = self.verify_invitation(request)

        if attempt_id:
            attempt = get_object_or_404(
                SubmissionAttempt.objects.select_related(
                    'submission', 'participant', 'evaluation'),
                id=attempt_id,
                participant=invitation.participant
            )
        else:
            attempt = SubmissionAttempt.objects.filter(
                participant=invitation.participant,
                evaluation=invitation.evaluation,
                is_completed=False
            ).order_by('-started_at').first()

            if not attempt:
                raise NotFound(
                    _("Aucune tentative active n'a été trouvée pour ce candidat"))

        if attempt.is_completed and not ended:
            raise ValidationError(_('Cette tentative est déjà terminée'))

        return attempt, invitation

    @extend_schema(
        request=None,
        parameters=[
            OpenApiParameter(name="payload", required=False, type=str)
        ],
        responses={201: SubmissionAttemptSerializer}
    )
    @action(detail=False, methods=['post'], url_path='start')
    def start_session(self, request):
        """Démarre une nouvelle session d'évaluation pour un candidat"""
        invitation = self.verify_invitation(request)

        attempt, created = SubmissionAttempt.objects.get_or_create(
            evaluation=invitation.evaluation,
            participant=invitation.participant,
        )

        if invitation.current is not None:
            invitation.current.status = EvaluationInvitation.Status.ACCEPTED
            invitation.current.save()

        if not created and attempt.is_completed:
            return Response(data={'message': _('Vous avez déjà passé cette évaluation')},
                            status=status.HTTP_406_NOT_ACCEPTABLE)
        elif attempt and not created:
            return Response(data=SubmissionAttemptSerializer(attempt).data)

        serializer = SubmissionAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=AnswerSerializer(many=True),
        parameters=[
            OpenApiParameter(name="payload", required=False, type=str)
        ],
        responses={200: AnswerSerializer}
    )
    @action(detail=False, methods=['post'], url_path=r'attempts/<int:attempt_id>/answers')
    @transaction.atomic
    def submit_answer(self, request, attempt_id=None):
        """Soumet une réponse à une question"""
        attempt, _ = self.verify_attempt(request, attempt_id)
        answers = []
        for answer in request.data:
            serializer = AnswerSerializer(data=answer)
            serializer.is_valid(raise_exception=True)

            question_id = serializer.validated_data.get('question').id
            if not attempt.evaluation.questions.filter(id=question_id).exists():
                return Response(
                    {"error": "Cette question n'appartient pas à cette évaluation"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            existing_answer = Answer.objects.filter(attempt=attempt, question_id=question_id).first()
            if existing_answer:
                return Response(
                    {"error": "Cette question a déjà été répondue"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            answers.append(serializer.save(attempt=attempt))

        return Response(status=status.HTTP_200_OK, data=AnswerSerializer(answers, many=True).data)

    @extend_schema(request=None, responses={200: SubmissionAttemptDetailSerializer})
    @action(detail=False, methods=['post'], url_path=r'attempts/<int:attempt_id>/finalize')
    @transaction.atomic
    def finish(self, request, attempt_id=None):
        """Termine l'évaluation"""
        attempt, _ = self.verify_attempt(request, attempt_id)

        questions_count = attempt.questions.count()
        answers_count = attempt.answers.count()

        if answers_count < questions_count:
            raise ValidationError(
                'Toutes les questions n\'ont pas été répondues ({}/{})'.format(
                    answers_count, questions_count)
            )

        submission = Submission.objects.create()

        attempt.submission = submission
        attempt.ended_at = timezone.now()
        attempt.is_completed = True
        attempt.save()
        correct_submission(submission, attempt)
        serializer = SubmissionAttemptDetailSerializer(attempt)
        return Response(serializer.data)
