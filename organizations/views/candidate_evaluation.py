from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiRequest
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from corrector import correct_submission
from organizations.models import (
    EvaluationInvitation, OrgSubmissionAttempt, OrgAnswer, OrgSubmission
)
from organizations.serializers import (
    OrgSubmissionAttemptSerializer, OrgAnswerSerializer,
    OrgSubmissionSerializer
)


@extend_schema_view(
    retrieve=extend_schema(
        description="Récupère les détails d'une évaluation pour un candidat via un token d'invitation",
        parameters=[
            OpenApiParameter(
                name="token", location=OpenApiParameter.PATH, required=True, type=str)
        ]
    ),
)
class CandidateEvaluationView(viewsets.GenericViewSet):
    """Vue pour les candidats qui passent une évaluation avec un token d'invitation"""

    # lookup_field = 'token'

    def get_serializer_class(self):
        if self.action == 'submit_answer':
            return OrgAnswerSerializer
        elif self.action == 'finish':
            return OrgSubmissionSerializer
        elif self.action == 'start_session':
            return OrgSubmissionAttemptSerializer
        return None

    @staticmethod
    def verify_invitation(token):
        """Vérifie si l'invitation est valide"""
        invitation = get_object_or_404(
            EvaluationInvitation.objects.select_related(
                'evaluation', 'candidate'),
            token=token
        )

        # Vérifier que l'invitation est valide
        if invitation.status not in (EvaluationInvitation.Status.PENDING, EvaluationInvitation.Status.ACCEPTED):
            raise PermissionDenied(
                _("Cette invitation n'est plus valide (status: {})").format(invitation.status))

        if timezone.now() > invitation.expires_at:
            invitation.status = EvaluationInvitation.Status.EXPIRED
            invitation.save()
            raise PermissionDenied(_("Cette invitation a expiré"))

        return invitation

    def verify_attempt(self, token, attempt_id=None, ended=False):
        """Vérifie si la tentative existe et appartient au candidat associé au token"""
        invitation = self.verify_invitation(token)

        if attempt_id:
            attempt = get_object_or_404(
                OrgSubmissionAttempt.objects.select_related(
                    'submission', 'candidate', 'evaluation'),
                id=attempt_id,
                candidate=invitation.candidate
            )
        else:
            attempt = OrgSubmissionAttempt.objects.filter(
                candidate=invitation.candidate,
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
        request=OpenApiRequest(),
        responses={201: OrgSubmissionAttemptSerializer}
    )
    @action(detail=False, methods=['post'], url_path='start')
    def start_session(self, request, token=None):
        """Démarre une nouvelle session d'évaluation pour un candidat"""
        invitation = self.verify_invitation(token)

        attempt, created = OrgSubmissionAttempt.objects.get_or_create(
            evaluation=invitation.evaluation,
            candidate=invitation.candidate,
        )

        if not created and attempt.is_completed:
            return Response(data={'message': _('Vous avez déjà passé cette évaluation')},
                            status=status.HTTP_406_NOT_ACCEPTABLE)
        elif attempt and not created:
            return Response(data=OrgSubmissionAttemptSerializer(attempt).data)

        serializer = OrgSubmissionAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=OrgAnswerSerializer(many=True), responses={200: OrgAnswerSerializer})
    @action(detail=False, methods=['post'], url_path=r'attempts/(?P<attempt_id>\d+)/answers')
    @transaction.atomic
    def submit_answer(self, request, token=None, attempt_id=None):
        """Soumet une réponse à une question"""
        attempt, _ = self.verify_attempt(token, attempt_id)
        answers = []
        for answer in request.data:
            serializer = OrgAnswerSerializer(data=answer)
            serializer.is_valid(raise_exception=True)

            question_id = serializer.validated_data.get('question').id
            if not attempt.evaluation.questions.filter(id=question_id).exists():
                return Response(
                    {"error": "Cette question n'appartient pas à cette évaluation"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            existing_answer = OrgAnswer.objects.filter(
                attempt=attempt, question_id=question_id).first()
            if existing_answer:
                return Response(
                    {"error": "Cette question a déjà été répondue"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            answers.append(serializer.save(attempt=attempt))

        return Response(status=status.HTTP_200_OK, data=OrgAnswerSerializer(answers, many=True).data)

    @extend_schema(request=OpenApiRequest(), responses={200: OrgSubmissionSerializer})
    @action(detail=False, methods=['post'], url_path=r'attempts/(?P<attempt_id>\d+)/finalize')
    @transaction.atomic
    def finish(self, request, token=None, attempt_id=None):
        """Termine l'évaluation"""
        attempt, _ = self.verify_attempt(token, attempt_id)

        questions_count = attempt.questions.count()
        answers_count = attempt.answers.count()

        if answers_count < questions_count:
            raise ValidationError(
                _('Toutes les questions n\'ont pas été répondues ({}/{})').format(
                    answers_count, questions_count)
            )

        submission = OrgSubmission.objects.create()

        attempt.submission = submission
        attempt.ended_at = timezone.now()
        attempt.is_completed = True
        attempt.save()
        correct_submission(submission, attempt)
        serializer = OrgSubmissionSerializer(submission)
        return Response(serializer.data)
