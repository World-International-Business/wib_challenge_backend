from datetime import timedelta
import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.jobs.agent_serializers import (
    AgentEventSerializer, BookingCreateSerializer, ConsentSerializer, ConsentUpdateSerializer,
    OrganizationInputSerializer, OTPInputSerializer, PrivacyRequestSerializer,
    RetentionSerializer, ReviewRequestSerializer, SlotSelectionSerializer,
    ReviewResponseSerializer, DashboardStatsSerializer, PublicSlotsSerializer,
    BookingCreatedSerializer, BookedSerializer, OTPSentSerializer, OTPVerifiedSerializer,
    RetentionResponseSerializer, OnboardingUpdateSerializer, OnboardingResponseSerializer,
)
from apps.jobs.models import (
    AgentEvent, BookingOption, ComplianceConsent, ComplianceRequest, ContractOTP,
    InterviewBooking, InterviewSlot, JobApplication, RetentionPolicy,
)
from apps.organizations.models import Organization
from services.agent_workflow import record_event, set_human_review
from services.recruitment_decisions import DecisionConflict, require_recruiter


def recruiter_organization(user):
    organization = getattr(user, 'organization', None)
    if not organization:
        raise PermissionDenied('Un compte organisation est requis.')
    return organization


def scoped_applications(user):
    if user.is_staff:
        return JobApplication.objects.all()
    organization = recruiter_organization(user)
    return JobApplication.objects.filter(job_offer__company=organization)


def authorized_organization(user, pk):
    organization = get_object_or_404(Organization, pk=pk)
    if not (user.is_staff or organization.account_id == user.pk or
            JobApplication.objects.filter(user=user, job_offer__company=organization).exists()):
        raise PermissionDenied('Organisation inaccessible.')
    return organization


@extend_schema_view(get=extend_schema(tags=['Agent'], parameters=[OpenApiParameter('after_id', int)]))
class AuditList(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AgentEventSerializer

    def get_queryset(self):
        events = AgentEvent.objects.all()
        if getattr(self, 'swagger_fake_view', False):
            return events.none()
        if not self.request.user.is_staff:
            events = events.filter(organization=recruiter_organization(self.request.user))
        after = self.request.query_params.get('after_id', self.request.query_params.get('afterId'))
        if after is not None:
            try:
                after = int(after)
            except (ValueError, TypeError):
                raise ValidationError({'after_id': 'Identifiant entier attendu.'})
            if after < 0:
                raise ValidationError({'after_id': 'Identifiant positif ou nul attendu.'})
            events = events.filter(pk__gt=after).order_by('pk')
        return events


@extend_schema_view(get=extend_schema(tags=['Agent'], responses=DashboardStatsSerializer))
class DashboardStats(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        applications = scoped_applications(request.user)
        counts = dict(applications.values('status').annotate(count=Count('pk')).values_list('status', 'count'))
        total = sum(counts.values())
        accepted = counts.get('accepted', 0)
        duration = ExpressionWrapper(F('contract_signed_at') - F('submitted_at'), output_field=DurationField())
        average = applications.filter(contract_signed_at__isnull=False).aggregate(value=Avg(duration))['value']
        return Response({
            'total_applications': total,
            'by_status': {key: counts.get(key, 0) for key in JobApplication.ApplicationStatus.values},
            'needs_human_review': applications.filter(needs_human_review=True).count(),
            'accepted_conversion_rate': round(accepted / total, 4) if total else None,
            'average_days_to_signed_contract': round(average.total_seconds() / 86400, 2) if average else None,
            'signed_contracts': applications.filter(contract_signed_at__isnull=False).count(),
        })


@extend_schema_view(
    post=extend_schema(tags=['Agent'], request=ReviewRequestSerializer, responses=ReviewResponseSerializer),
    delete=extend_schema(tags=['Agent'], request=ReviewRequestSerializer, responses=ReviewResponseSerializer),
)
class HumanReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(scoped_applications(request.user), pk=pk)
        require_recruiter(application, request.user)
        serializer = ReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = set_human_review(application.pk, reason=serializer.validated_data['reason'], actor=request.user)
        return Response({'needs_human_review': application.needs_human_review, 'review_reason': application.review_reason})

    def delete(self, request, pk):
        application = get_object_or_404(scoped_applications(request.user), pk=pk)
        serializer = ReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = set_human_review(application.pk, reason=serializer.validated_data['reason'], actor=request.user, required=False)
        return Response({'needs_human_review': application.needs_human_review})


@extend_schema_view(
    get=extend_schema(tags=['Compliance'], responses=ConsentSerializer(many=True)),
    patch=extend_schema(tags=['Compliance'], request=ConsentUpdateSerializer, responses=ConsentSerializer),
)
class ConsentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ConsentSerializer(ComplianceConsent.objects.filter(user=request.user), many=True).data)

    @transaction.atomic
    def patch(self, request):
        serializer = ConsentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        organization = authorized_organization(request.user, data['organization'])
        consent, _ = ComplianceConsent.objects.update_or_create(
            user=request.user, organization=organization, purpose=data['purpose'], defaults={'granted': data['granted']},
        )
        AgentEvent.objects.create(organization=organization, actor='human', human_validator=request.user,
                                  action='consent.updated', target_id=str(consent.pk),
                                  input_data={'purpose': consent.purpose, 'granted': consent.granted})
        return Response(ConsentSerializer(consent).data)


@extend_schema_view(
    get=extend_schema(tags=['Compliance'], responses=PrivacyRequestSerializer(many=True)),
    post=extend_schema(tags=['Compliance'], request=OrganizationInputSerializer, responses={201: PrivacyRequestSerializer, 200: PrivacyRequestSerializer}),
)
class PrivacyRequestView(APIView):
    permission_classes = [IsAuthenticated]
    kind = 'access'

    def get(self, request):
        return Response(PrivacyRequestSerializer(
            ComplianceRequest.objects.filter(user=request.user, kind=self.kind), many=True,
        ).data)

    @transaction.atomic
    def post(self, request):
        serializer = OrganizationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = authorized_organization(request.user, serializer.validated_data['organization'])
        privacy_request, created = ComplianceRequest.objects.get_or_create(
            user=request.user, organization=organization, kind=self.kind, status='pending',
        )
        if created:
            AgentEvent.objects.create(organization=organization, actor='human', human_validator=request.user,
                                      action=f'privacy.{self.kind}_requested', target_id=str(privacy_request.pk))
        return Response(PrivacyRequestSerializer(privacy_request).data, status=201 if created else 200)


class DeletionRequestView(PrivacyRequestView):
    kind = 'deletion'


@extend_schema_view(
    get=extend_schema(tags=['Compliance'], responses=RetentionResponseSerializer),
    put=extend_schema(tags=['Compliance'], request=RetentionSerializer, responses=RetentionResponseSerializer),
)
class RetentionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = recruiter_organization(request.user)
        policy = RetentionPolicy.objects.filter(organization=organization).first()
        if not policy:
            return Response({'candidate_days': None, 'talent_pool_days': None, 'configured': False})
        return Response({**RetentionSerializer(policy).data, 'configured': True})

    @transaction.atomic
    def put(self, request):
        organization = recruiter_organization(request.user)
        Organization.objects.select_for_update().get(pk=organization.pk)
        serializer = RetentionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not {'candidate_days', 'talent_pool_days'}.issubset(serializer.validated_data):
            raise ValidationError('Les deux durées de conservation sont requises.')
        policy, _ = RetentionPolicy.objects.update_or_create(
            organization=organization, defaults={**serializer.validated_data, 'updated_by': request.user},
        )
        AgentEvent.objects.create(organization=organization, actor='human', human_validator=request.user,
                                  action='retention.updated', target_id=str(policy.pk), input_data=serializer.validated_data)
        return Response({**RetentionSerializer(policy).data, 'configured': True})


@extend_schema_view(
    get=extend_schema(tags=['Onboarding'], responses=OnboardingResponseSerializer),
    patch=extend_schema(tags=['Onboarding'], request=OnboardingUpdateSerializer, responses=OnboardingResponseSerializer),
)
class OnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def get_application(self, request, pk):
        applications = JobApplication.objects.select_related('job_offer')
        if not request.user.is_staff:
            organization = getattr(request.user, 'organization', None)
            applications = applications.filter(job_offer__company=organization) if organization else applications.filter(
                user=request.user, status='accepted',
            )
        return get_object_or_404(applications, pk=pk)

    def get(self, request, pk):
        from services.onboarding import onboarding_snapshot

        return Response(onboarding_snapshot(self.get_application(request, pk)))

    def patch(self, request, pk):
        from services.onboarding import update_onboarding

        application = self.get_application(request, pk)
        require_recruiter(application, request.user)
        serializer = OnboardingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(update_onboarding(application.pk, request.user, serializer.validated_data))


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class PublicTokenThrottle(AnonRateThrottle):
    rate = '20/min'


@extend_schema_view(post=extend_schema(tags=['Interviews'], request=BookingCreateSerializer, responses={201: BookingCreatedSerializer}))
class BookingCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        application = get_object_or_404(scoped_applications(request.user).select_related('job_offer'), pk=pk)
        require_recruiter(application, request.user)
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = Organization.objects.select_for_update().get(pk=application.job_offer.company_id)
        intervals = serializer.validated_data['slots']
        now = timezone.now()
        slots = []
        for interval in intervals:
            start, end = interval['starts_at'], interval['ends_at']
            if start <= now or end <= start or end - start > timedelta(hours=8):
                raise ValidationError('Créneaux futurs, positifs et limités à huit heures requis.')
            if any(start < other.ends_at and end > other.starts_at for other in slots):
                raise ValidationError('Les créneaux proposés se chevauchent.')
            slot, _ = InterviewSlot.objects.get_or_create(organization=organization, starts_at=start, ends_at=end)
            if InterviewBooking.objects.filter(selected_slot__organization=organization,
                                                selected_slot__starts_at__lt=end, selected_slot__ends_at__gt=start).exists():
                raise ValidationError('Un créneau chevauche un entretien réservé.')
            slots.append(slot)
        token = secrets.token_urlsafe(32)
        booking = InterviewBooking.objects.create(application=application, token_hash=token_digest(token),
                                                   expires_at=now + timedelta(days=7))
        BookingOption.objects.bulk_create([BookingOption(booking=booking, slot=slot) for slot in slots])
        record_event(application, 'interview.slots_created', actor=request.user, data={'booking_id': booking.pk})
        return Response({'token': token, 'expires_at': booking.expires_at, 'booking_id': booking.pk}, status=201)


def public_booking(token):
    booking = get_object_or_404(InterviewBooking.objects.select_related('application__job_offer'), token_hash=token_digest(token))
    if booking.expires_at <= timezone.now():
        raise NotFound('Lien indisponible ou expiré.')
    return booking


@extend_schema_view(get=extend_schema(tags=['Interviews'], responses=PublicSlotsSerializer))
class InterviewSlotsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicTokenThrottle]

    def get(self, request, token):
        booking = public_booking(token)
        slots = []
        for option in booking.options.select_related('slot'):
            slot = option.slot
            occupied = InterviewBooking.objects.filter(selected_slot__organization_id=slot.organization_id,
                selected_slot__starts_at__lt=slot.ends_at, selected_slot__ends_at__gt=slot.starts_at).exists()
            if not occupied and slot.starts_at > timezone.now():
                slots.append({'id': slot.pk, 'starts_at': slot.starts_at, 'ends_at': slot.ends_at})
        return Response({'slots': slots, 'booked': booking.booked_at is not None, 'expires_at': booking.expires_at})


@extend_schema_view(post=extend_schema(tags=['Interviews'], request=SlotSelectionSerializer, responses=BookedSerializer))
class InterviewBookView(InterviewSlotsView):
    @transaction.atomic
    def post(self, request, token):
        initial = public_booking(token)
        organization_id = initial.application.job_offer.company_id
        Organization.objects.select_for_update().get(pk=organization_id)
        booking = InterviewBooking.objects.select_for_update().select_related('application__job_offer').get(pk=initial.pk)
        if booking.expires_at <= timezone.now():
            raise NotFound('Lien indisponible ou expiré.')
        if booking.booked_at:
            raise DecisionConflict('Ce lien de réservation a déjà été utilisé.')
        serializer = SlotSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        option = get_object_or_404(booking.options.select_related('slot'), slot_id=serializer.validated_data['slot_id'])
        slot = option.slot
        if slot.starts_at <= timezone.now():
            raise ValidationError('Créneau passé.')
        if InterviewBooking.objects.filter(selected_slot__organization_id=organization_id,
                selected_slot__starts_at__lt=slot.ends_at, selected_slot__ends_at__gt=slot.starts_at).exists():
            raise DecisionConflict('Créneau déjà réservé.')
        booking.selected_slot = slot
        booking.booked_at = timezone.now()
        booking.save(update_fields=['selected_slot', 'booked_at'])
        application = JobApplication.objects.select_for_update().select_related('job_offer').get(pk=booking.application_id)
        application.interview_date = slot.starts_at
        application.interview_duration = int((slot.ends_at - slot.starts_at).total_seconds() / 60)
        application.save(update_fields=['interview_date', 'interview_duration', 'updated_at'])
        record_event(application, 'interview.booked', data={'slot_id': slot.pk}, human=True)
        return Response({'booked': True, 'starts_at': slot.starts_at, 'ends_at': slot.ends_at})


def contract_application(token, *, lock=False):
    applications = JobApplication.objects.select_related('job_offer')
    if lock:
        applications = applications.select_for_update()
    application = get_object_or_404(applications, contract_token=token)
    if (not application.contract_token_expires_at or application.contract_token_expires_at <= timezone.now()
            or application.contract_status != JobApplication.ContractStatus.SENT or not application.contract_file):
        raise NotFound('Contrat indisponible ou expiré.')
    return application


def contract_otp_verified(application):
    otp = ContractOTP.objects.filter(application=application, token_hash=token_digest(application.contract_token)).first()
    return bool(otp and otp.verified_at and otp.verified_at > timezone.now() - timedelta(minutes=15)
                and otp.expires_at > timezone.now())


@extend_schema_view(post=extend_schema(tags=['Contracts'], request=None, responses=OTPSentSerializer))
class RequestOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicTokenThrottle]

    @transaction.atomic
    def post(self, request, token):
        application = contract_application(token, lock=True)
        otp = ContractOTP.objects.filter(application=application).first()
        now = timezone.now()
        if otp and otp.token_hash == token_digest(token):
            if otp.attempts >= 5 or otp.sends >= 5:
                return Response({'detail': 'Limite atteinte. Demandez un nouveau lien au recruteur.'}, status=429)
            if now < otp.created_at + timedelta(seconds=60):
                return Response({'detail': 'Veuillez patienter avant un nouvel envoi.'}, status=429)
        code = f'{secrets.randbelow(1000000):06d}'
        try:
            sent = send_mail('Code de confirmation du contrat',
                f'Votre code de confirmation est {code}. Il expire dans 10 minutes. Ne le partagez pas.',
                settings.DEFAULT_FROM_EMAIL, [application.applicant_email], fail_silently=False)
            if not sent:
                raise RuntimeError('mail_not_accepted')
        except Exception:
            return Response({'detail': 'Envoi impossible. Réessayez plus tard.'}, status=503)
        same_token = bool(otp and otp.token_hash == token_digest(token))
        ContractOTP.objects.update_or_create(application=application, defaults={
            'token_hash': token_digest(token), 'code_hash': make_password(code),
            'created_at': now, 'expires_at': now + timedelta(minutes=10),
            'attempts': otp.attempts if same_token else 0,
            'sends': otp.sends + 1 if same_token else 1, 'verified_at': None,
        })
        record_event(application, 'contract.otp_requested')
        return Response({'status': 'sent', 'expires_in': 600})


@extend_schema_view(post=extend_schema(tags=['Contracts'], request=OTPInputSerializer, responses=OTPVerifiedSerializer))
class VerifyOTPView(RequestOTPView):
    @transaction.atomic
    def post(self, request, token):
        application = contract_application(token, lock=True)
        otp = ContractOTP.objects.select_for_update().filter(application=application, token_hash=token_digest(token)).first()
        if not otp or otp.expires_at <= timezone.now():
            return Response({'detail': 'Code indisponible ou expiré.'}, status=400)
        if otp.attempts >= 5:
            return Response({'detail': 'Nombre de tentatives dépassé.'}, status=429)
        if otp.verified_at:
            return Response({'detail': 'Code déjà utilisé.'}, status=409)
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        serializer = OTPInputSerializer(data=request.data)
        if not serializer.is_valid() or not check_password(serializer.validated_data['code'], otp.code_hash):
            return Response({'detail': 'Code invalide.'}, status=400)
        otp.verified_at = timezone.now()
        otp.save(update_fields=['verified_at'])
        record_event(application, 'contract.otp_verified', human=True)
        return Response({'verified': True})
