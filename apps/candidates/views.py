import os

from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response

from apps.learning.models import Certificate, CourseEnrollment
from apps.jobs.models import JobApplication

from apps.candidates.filters import (
    CandidateProfileFilterSet, ExperienceFilterSet, EducationFilterSet, ProjectFilterSet, LanguageFilterSet
)
from apps.candidates.models import CandidateProfile, Experience, Education, Language, Project, ProfileTechnology
from apps.candidates.serializers import CandidateProfileSerializer, ExperienceSerializer, EducationSerializer, \
    LanguageSerializer, ProjectSerializer, ProfileTechnologySerializer
from wib_challenge.permissions import IsOwner, ReadOnly


@extend_schema(
    tags=["Profil Candidats/Professionels"]
)
class CandidateProfileViewSet(viewsets.ModelViewSet):
    queryset = (CandidateProfile.objects
                .prefetch_related('profile_technologies', 'profession')
                .select_related('user').all()
                )
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwner | ReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CandidateProfileFilterSet
    search_fields = [
        'user__first_name', 'user__last_name', 'user__email',
        'location', 'short_bio', 'biography', 'interested_by',
        'profession__title'
    ]
    ordering_fields = [
        'created_at', 'updated_at', 'years_experience',
        'highest_degree', 'user__first_name', 'profession__title'
    ]
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user__is_staff=False, user__is_active=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path=r'user/(?P<user_id>\d+)')
    def get_by_user(self, request, user_id: int):
        profile = get_object_or_404(self.get_queryset(), user=user_id)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    def _get_or_create_profile(self, user):
        profile, _ = CandidateProfile.objects.get_or_create(user=user, defaults={
            'profession_id': 1,
            'first_name': user.first_name,
            'last_name': user.last_name,
        })
        return profile

    @action(detail=False, methods=['get'], url_path='me/dashboard', permission_classes=[IsAuthenticated])
    def dashboard(self, request):
        profile = get_object_or_404(CandidateProfile, user=request.user)

        missing = []
        if not profile.biography:
            missing.append('biography')
        if not profile.profession:
            missing.append('profession')
        if not profile.years_experience:
            missing.append('years_experience')

        total_fields = ['first_name', 'last_name', 'biography', 'profession', 'years_experience']
        filled = sum([bool(getattr(profile, f, None)) for f in total_fields])
        completion = int((filled / len(total_fields)) * 100)

        completed_courses_count = CourseEnrollment.objects.filter(
            user=request.user, status=CourseEnrollment.Status.COMPLETED
        ).count()
        certificates_count = Certificate.objects.filter(user=request.user, status=Certificate.Status.ISSUED).count()

        applications_by_status = JobApplication.objects.filter(user=request.user).values('status').annotate(count=Count('id'))
        applications_summary = {item['status']: item['count'] for item in applications_by_status}

        return Response({
            'profile_completion_percentage': completion,
            'missing_profile_fields': missing,
            'steps': {
                'account_created': True,
                'profile_completed': completion >= 80,
                'evaluation_completed': False,
                'orientation_completed': False,
                'has_job_applications': JobApplication.objects.filter(user=request.user).exists(),
            },
            'completed_courses_count': completed_courses_count,
            'certificates_count': certificates_count,
            'applications_count': JobApplication.objects.filter(user=request.user).count(),
            'applications_by_status': applications_summary,
        })

    @action(detail=False, methods=['get'], url_path='me/certificates', permission_classes=[IsAuthenticated])
    def certificates(self, request):
        certs = Certificate.objects.filter(user=request.user, status=Certificate.Status.ISSUED)
        data = [{
            'id': c.id,
            'certificate_number': c.certificate_number,
            'course_title': c.course_title_snapshot,
            'issued_at': c.issued_at,
            'verification_code': c.verification_code,
            'download_url': request.build_absolute_uri(c.pdf_file.url) if c.pdf_file else None,
        } for c in certs]
        return Response(data)

    @action(detail=False, methods=['post', 'get', 'delete'], url_path='me/resume', permission_classes=[IsAuthenticated])
    def resume(self, request):
        profile = get_object_or_404(CandidateProfile, user=request.user)

        if request.method == 'GET':
            if not profile.resume:
                return Response({'code': 'RESUME_NOT_FOUND', 'detail': 'Aucun CV enregistré.'}, status=status.HTTP_404_NOT_FOUND)
            return Response({
                'resume_url': request.build_absolute_uri(profile.resume.url),
                'name': os.path.basename(profile.resume.name),
            })

        if request.method == 'DELETE':
            if profile.resume:
                profile.resume.delete(save=False)
                profile.resume = None
                profile.save(update_fields=['resume', 'updated_at'])
            return Response(status=status.HTTP_204_NO_CONTENT)

        # POST
        file = request.FILES.get('file')
        if not file:
            return Response({'code': 'INVALID_RESUME', 'detail': 'Aucun fichier fourni.', 'fieldErrors': {}, 'metadata': {}}, status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(file.name)[1].lower()
        if ext != '.pdf':
            return Response({'code': 'INVALID_RESUME', 'detail': 'Le CV doit être au format PDF.', 'fieldErrors': {}, 'metadata': {}}, status=status.HTTP_400_BAD_REQUEST)

        max_size = 5 * 1024 * 1024
        if file.size > max_size:
            return Response({'code': 'INVALID_RESUME', 'detail': 'Le fichier dépasse 5 Mo.', 'fieldErrors': {}, 'metadata': {}}, status=status.HTTP_400_BAD_REQUEST)

        if hasattr(file, 'content_type') and file.content_type not in ['application/pdf', 'application/octet-stream']:
            pass

        if profile.resume:
            profile.resume.delete(save=False)
        profile.resume.save(f"resume_{request.user.id}_{timezone.now().timestamp()}.pdf", file, save=True)

        return Response({
            'resume_url': request.build_absolute_uri(profile.resume.url),
            'name': os.path.basename(profile.resume.name),
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='me/cv-data', permission_classes=[IsAuthenticated])
    def cv_data(self, request):
        profile = get_object_or_404(CandidateProfile, user=request.user)
        certs = Certificate.objects.filter(user=request.user, status=Certificate.Status.ISSUED)
        return Response({
            'identity': {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': profile.user.phone if hasattr(profile.user, 'phone') else '',
                'location': profile.location,
            },
            'profession': profile.profession.title if profile.profession else None,
            'summary': profile.biography,
            'experiences': ExperienceSerializer(profile.experiences.all(), many=True).data,
            'educations': EducationSerializer(profile.educations.all(), many=True).data,
            'skills': [{'name': pt.technology.name, 'level': pt.level} for pt in profile.profile_technologies.all()],
            'projects': ProjectSerializer(profile.projects.all(), many=True).data,
            'languages': [{'name': l.name, 'level': l.level} for l in profile.languages.all()],
            'certificates': [{
                'certificate_number': c.certificate_number,
                'course_title': c.course_title_snapshot,
                'issued_at': c.issued_at,
                'verification_code': c.verification_code,
            } for c in certs],
            'resume_url': request.build_absolute_uri(profile.resume.url) if profile.resume else None,
        })


@extend_schema(
    tags=["Profil Candidats/Professionels"]
)
class NestedProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwner | ReadOnly]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        get_object_or_404(CandidateProfile, pk=self.kwargs['profile_pk'])
        return self.queryset.filter(profile=self.kwargs['profile_pk'])

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


class ProfileTechnologyViewSet(NestedProfileViewSet):
    queryset = ProfileTechnology.objects.all()
    serializer_class = ProfileTechnologySerializer
    ordering = ['-level']


class ExperienceViewSet(NestedProfileViewSet):
    queryset = Experience.objects.select_related('profile__user').all()
    serializer_class = ExperienceSerializer

    filterset_class = ExperienceFilterSet
    search_fields = [
        'title', 'company', 'description', 'location'
    ]
    ordering_fields = [
        'start_date', 'end_date', 'title', 'company', 'created_at'
    ]
    ordering = ['-start_date', '-end_date']


class EducationViewSet(NestedProfileViewSet):
    queryset = Education.objects.select_related('profile__user').all()
    serializer_class = EducationSerializer

    filterset_class = EducationFilterSet
    search_fields = [
        'name', 'diploma', 'speciality'
    ]
    ordering_fields = [
        'year_of_graduation', 'name', 'diploma', 'created_at'
    ]
    ordering = ['-year_of_graduation', 'name']


class LanguageViewSet(NestedProfileViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer

    filterset_class = LanguageFilterSet
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'created_at']
    ordering = ['name']


class ProjectViewSet(NestedProfileViewSet):
    queryset = Project.objects.prefetch_related('images').select_related('profile__user').all()
    serializer_class = ProjectSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    filterset_class = ProjectFilterSet
    search_fields = [
        'name', 'description'
    ]
    ordering_fields = [
        'start_date', 'name', 'created_at'
    ]
    ordering = ['-start_date', 'name']


@extend_schema(
    parameters=[
        OpenApiParameter(name='project_id', type=int),
    ],
    tags=["Profil Candidats/Professionels"]
)
class ProjectImageViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    parser_classes = [MultiPartParser, FormParser]

    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        project_id = self.request.GET.get('project_id', None)
        if project_id:
            return self.queryset.filter(project_id=project_id)
        return super().get_queryset()
        