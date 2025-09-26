from dataclasses import dataclass
import json
from datetime import datetime
import logging

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
from services.redis_stream import publish_json, STREAM_KEY as REDIS_STREAM_KEY
from apps.candidates.models import CandidateProfile
from apps.candidates.serializers import CandidateProfileSerializer

logger = logging.getLogger(__name__)

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
        logger.info("finish() appelé", extra={"attempt_id": attempt_id, "path": request.get_full_path()})
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
        # Correction et sérialisation
        correct_submission(submission, attempt)

        # Journalisation sur Redis si la moyenne > 10/20
        try:
            evaluation = attempt.evaluation
            max_score = evaluation.max_score
            score = attempt.submission.score or 0
            avg_on_20 = (score * 20.0 / max_score) if max_score else 0

            logger.info(
                "Résultat évaluation: attempt_id=%s evaluation_id=%s score=%s max_score=%s avg_on_20=%.2f",
                attempt.id,
                (evaluation.id if evaluation else None),
                score,
                max_score,
                (avg_on_20 if isinstance(avg_on_20, (int, float)) else 0),
            )

            if avg_on_20 >= 0:
                # Récupérer exactement le JSON de l'endpoint profil (CandidateProfileSerializer)
                if not attempt.participant:
                    logger.warning("Pas de participant lié à la tentative — rien à publier", extra={"attempt_id": attempt.id})
                if attempt.participant and getattr(attempt.participant, "user", None):
                    user = attempt.participant.user
                    profile: CandidateProfile | None = getattr(user, "profile", None)
                    if profile:
                        # Construire le payload selon le schéma requis par le consumer
                        try:
                            # Récupérer profession sous forme de chaîne
                            profession_str = None
                            try:
                                profession_str = profile.profession.title  # type: ignore[attr-defined]
                            except Exception:
                                profession_str = str(getattr(profile, "profession_id", "") or "")

                            # Récupérer la représentation user (email/username/id)
                            user_str = (
                                getattr(user, "email", None)
                                or getattr(user, "username", None)
                                or str(getattr(user, "pk", ""))
                            )

                            # Extraire technologies avec niveau via la relation through
                            tech_items = []
                            try:
                                for tech in profile.technologies.all():
                                    through = profile.profile_technologies.filter(technology=tech).first()
                                    level = getattr(through, "level", 0)
                                    tech_items.append({
                                        "id": tech.id,
                                        "name": tech.name,
                                        "level": level or 0,
                                    })
                            except Exception:
                                tech_items = []

                            payload = {
                                "id": profile.id,
                                "profession": profession_str or "",
                                "user": user_str or "",
                                "technologies": tech_items,
                                "createdAt": (profile.created_at.isoformat() if hasattr(profile, "created_at") and profile.created_at else ""),
                                "updatedAt": (profile.updated_at.isoformat() if hasattr(profile, "updated_at") and profile.updated_at else ""),
                                "location": getattr(profile, "location", "") or "",
                                "shortBio": getattr(profile, "short_bio", "") or "",
                                "biography": getattr(profile, "biography", "") or "",
                                "disability": bool(getattr(profile, "disability", False)),
                                "openToWork": bool(getattr(profile, "open_to_work", False)),
                                "yearsExperience": getattr(profile, "years_experience", 0) or 0,
                                "otherYearsExperience": getattr(profile, "other_years_experience", 0) or 0,
                                "highestDegree": getattr(profile, "highest_degree", 0) or 0,
                                "interestedBy": getattr(profile, "interested_by", "") or "",
                            }
                        except Exception:
                            logger.exception("Erreur lors de la construction du payload profil")
                            payload = None

                        if payload is not None:
                            logger.info("Publication vers Redis", extra={
                                "stream": REDIS_STREAM_KEY,
                                "user_id": getattr(user, "id", None),
                                "profile_id": getattr(profile, "id", None),
                            })
                            ok = publish_json(REDIS_STREAM_KEY, payload)
                        if not ok:
                            logger.error("Échec publication Redis", extra={"stream": REDIS_STREAM_KEY})
                    else:
                        logger.warning("Utilisateur sans profil — rien à publier", extra={
                            "user_id": getattr(user, "id", None)
                        })
                else:
                    logger.warning("Participant sans user — rien à publier", extra={
                        "attempt_id": attempt.id
                    })
            else:
                logger.info(
                    "Non éligible à la publication: moyenne %.2f < 10 (score=%s / max=%s)",
                    (avg_on_20 if isinstance(avg_on_20, (int, float)) else 0),
                    score,
                    max_score,
                )
        except Exception:
            # Ne jamais casser la réponse API pour un échec de log
            logger.exception("Erreur inattendue lors de la publication Redis")

        serializer = SubmissionAttemptDetailSerializer(attempt)
        return Response(serializer.data)
