from django.db import transaction, IntegrityError
from django.db.models import Avg, Max
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response


from services.certificate_generator import generate_certificate_pdf
from services.learning_progress import complete_content, compute_course_progress, compute_blocking_reasons, get_next_content
from services.suggest_courses import suggest_courses_from_attempt
from apps.payments.models import Payment
from wib_challenge.pagination import paginated_response
from .filters import (
    CourseFilter, ModuleFilter, ContentFilter, QuizFilter, QuizQuestionFilter, QuizChoiceFilter,
    QuizResultFilter, ProgressFilter, CertificateFilter
)
from .models import (
    Course, Module, Content, Quiz, QuizQuestion, QuizChoice, QuizAnswer, QuizResult,
    Progress, Certificate, TrainingSelection,CourseEnrollment
)
from .serializers import (
    CourseSerializer, CourseListSerializer, ModuleSerializer, ContentDetailSerializer, ContentListSerializer,
    QuizSerializer, QuizPublicSerializer, QuizListSerializer, QuizQuestionSerializer,
    CourseEnrollmentSerializer, CourseAssignmentSerializer,
    QuizChoiceSerializer, QuizResultSerializer, ProgressSerializer, CertificateSerializer,
    CourseProgressSerializer, UserProgressStatsSerializer, QuizStatsSerializer,
    QuizSubmissionSerializer, CourseSuggestSerializer, ProgressUpdateSerializer
)
from ..evaluations.models import SubmissionAttempt


@extend_schema_view(
    list=extend_schema(
        summary="Liste des cours",
        description="Récupérer la liste paginée des cours avec filtres et recherche",
        tags=["Cours"],
        responses={200: CourseListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Détails d'un cours",
        description="Récupérer les détails complets d'un cours avec ses modules et contenus",
        tags=["Cours"],
        responses={
            200: CourseSerializer,
        }
    ),
    create=extend_schema(
        summary="Créer un cours",
        description="Créer un nouveau cours",
        tags=["Cours"],
        responses={
            201: CourseSerializer,
        }
    ),
    update=extend_schema(
        summary="Mettre à jour un cours",
        description="Mettre à jour complètement un cours",
        tags=["Cours"],
        responses={
            200: CourseSerializer,
        }
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement un cours",
        description="Mettre à jour partiellement un cours",
        tags=["Cours"],
        responses={
            200: CourseSerializer,
        }
    ),
    destroy=extend_schema(
        summary="Supprimer un cours",
        description="Supprimer définitivement un cours",
        tags=["Cours"],
        responses={
            204: None,
        }
    )
)

class CourseViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des cours"""
    queryset = Course.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CourseFilter
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'level']
    ordering = ['title']

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_published=True, is_active=True)
        is_selected = self.request.query_params.get('is_selected', None)

        if is_selected is not None and hasattr(self.request.user, 'organization'):
            if is_selected.lower() == 'true':
                return queryset.filter(selected_by_organizations=self.request.user.organization)
            elif is_selected.lower() == 'false':
                return queryset.exclude(selected_by_organizations=self.request.user.organization)

        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'assign_to_users']:
            return [permissions.IsAdminUser()]
        if self.action in ['enroll', 'progress', 'generate_certificate']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        course = self.get_object()
        if not course.is_free or course.price > 0:
            return Response(
                {'code': 'PAYMENT_REQUIRED', 'detail': 'Cette formation nécessite un paiement.', 'fieldErrors': {}, 'metadata': {}},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        enrollment, created = CourseEnrollment.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={'status': CourseEnrollment.Status.ACTIVE, 'source': CourseEnrollment.Source.SELF},
        )
        if enrollment.status in [CourseEnrollment.Status.CANCELLED, CourseEnrollment.Status.EXPIRED]:
            enrollment.status = CourseEnrollment.Status.ACTIVE
            enrollment.source = CourseEnrollment.Source.SELF
            enrollment.expires_at = None
            enrollment.save(update_fields=['status', 'source', 'expires_at', 'updated_at'])
        return Response({
            'id': enrollment.id,
            'courseId': course.id,
            'status': enrollment.status,
            'enrolledAt': enrollment.assigned_at,
            'accessGranted': enrollment.status == CourseEnrollment.Status.ACTIVE,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['POST'])
    def select(self, request, pk=None):
        """Sélectionner une formation"""
        course = self.get_object()
        if not hasattr(request.user, 'organization'):
            return Response(
                {'detail': 'Seules les organisations peuvent sélectionner des formations'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            TrainingSelection.objects.get_or_create(
                course=course,
                organization=request.user.organization,
                defaults={'is_active': True}
            )
            return Response({'message': 'Formation sélectionnée avec succès'})
        except IntegrityError:
            return Response(
                {'detail': 'Formation déjà sélectionnée'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['POST'])
    def unselect(self, request, pk=None):
        """Désélectionner une formation"""
        course = self.get_object()
        if not hasattr(request.user, 'organization'):
            return Response(
                {'detail': 'Seules les organisations peuvent désélectionner des formations'},
                status=status.HTTP_403_FORBIDDEN
            )

        selection = TrainingSelection.objects.filter(
            course=course,
            organization=request.user.organization
        ).first()

        if selection:
            selection.delete()
            return Response({'message': 'Formation désélectionnée avec succès'})
        return Response(
            {'detail': 'Formation non sélectionnée'},
            status=status.HTTP_404_NOT_FOUND
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        return CourseSerializer

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)

    @extend_schema(
        summary="Progrès du cours",
        description="Obtenir le progrès de l'utilisateur authentifié pour ce cours",
        tags=["Cours"],
        responses={
            200: CourseProgressSerializer,
        }
    )

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Obtenir le progrès de l'utilisateur pour ce cours"""
        course = self.get_object()
        enrollment = get_object_or_404(
            CourseEnrollment,
            user=request.user,
            course=course,
            status__in=[CourseEnrollment.Status.ACTIVE, CourseEnrollment.Status.COMPLETED],
        )
        data = compute_course_progress(request.user, course, enrollment)
        data['next_content'] = get_next_content(request.user, course)
        data['modules'] = []
        for module in course.modules.filter(is_active=True).order_by('order'):
            module_total = Content.objects.filter(module=module, is_active=True, is_required=True).count()
            module_completed = Progress.objects.filter(
                user=request.user, content__module=module, content__is_required=True, is_completed=True
            ).count()
            module_pct = round((module_completed / module_total * 100), 2) if module_total > 0 else 0
            data['modules'].append({
                'moduleId': module.id,
                'percentage': module_pct,
                'isCompleted': module_pct == 100 and module_total > 0,
            })
        return Response(data)

    @extend_schema(
        summary="État de complétion du cours",
        description="Indique si l'utilisateur peut obtenir son certificat",
        tags=["Cours"],
        responses={200: None},
    )
    @action(detail=True, methods=['get'], url_path='completion-status')
    def completion_status(self, request, pk=None):
        course = self.get_object()
        try:
            enrollment = CourseEnrollment.objects.get(
                user=request.user, course=course, status__in=[CourseEnrollment.Status.ACTIVE, CourseEnrollment.Status.COMPLETED]
            )
        except CourseEnrollment.DoesNotExist:
            return Response(
                {'code': 'ENROLLMENT_REQUIRED', 'detail': 'Inscription requise.', 'fieldErrors': {}, 'metadata': {}},
                status=status.HTTP_403_FORBIDDEN,
            )
        progress = compute_course_progress(request.user, course, enrollment)
        eligible = progress['is_completed']
        blocking = compute_blocking_reasons(request.user, course) if not eligible else []
        return Response({
            'eligible': eligible,
            'isCompleted': enrollment.status == CourseEnrollment.Status.COMPLETED,
            'completedAt': enrollment.completed_at,
            'blockingReasons': blocking,
            'finalScore': progress['percentage'],
            'certificate': {'status': 'available'} if eligible else {'status': 'not_eligible'},
        })

    @extend_schema(
        summary="Éligibilité au certificat",
        description="Indique si le certificat est disponible, payant, et son identifiant",
        tags=["Cours"],
        responses={200: None},
    )
    @action(detail=True, methods=['get'], url_path='certificate/eligibility')
    def certificate_eligibility(self, request, pk=None):
        course = self.get_object()
        try:
            enrollment = CourseEnrollment.objects.get(
                user=request.user, course=course, status=CourseEnrollment.Status.COMPLETED
            )
        except CourseEnrollment.DoesNotExist:
            return Response(
                {'code': 'COURSE_NOT_COMPLETED', 'detail': 'La formation doit être terminée.', 'fieldErrors': {}, 'metadata': {}},
                status=status.HTTP_403_FORBIDDEN,
            )

        payment_required = course.certificate_enabled and course.certificate_price > 0
        price = course.certificate_price if payment_required else 0

        certificate, _ = Certificate.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={
                'enrollment': enrollment,
                'status': Certificate.Status.PAYMENT_PENDING if payment_required else Certificate.Status.ELIGIBLE,
                'payment_required': payment_required,
                'participant_name_snapshot': request.user.get_full_name() or request.user.email,
                'course_title_snapshot': course.title,
                'level_snapshot': course.level,
                'duration_snapshot': str(course.estimated_duration or ''),
                'final_score': compute_course_progress(request.user, course, enrollment)['percentage'],
            },
        )

        blocking = []
        if certificate.status == Certificate.Status.REVOKED:
            blocking.append({'type': 'certificate_revoked', 'label': 'Le certificat a été révoqué.'})

        return Response({
            'eligible': True,
            'paymentRequired': payment_required,
            'price': str(price),
            'currency': course.currency,
            'certificateId': certificate.id,
            'status': certificate.status,
            'blockingReasons': blocking,
        })

    @extend_schema(
        summary="Générer un certificat",
        description="Générer un certificat pour ce cours si l'utilisateur l'a terminé",
        tags=["Cours"],
        responses={
            201: CertificateSerializer,
        }
    )
    
    @extend_schema(
        summary="Assigner une formation à des utilisateurs",
        description="Assigner une formation à un ou plusieurs utilisateurs avec création de notifications",
        tags=["Cours"],
        request=CourseAssignmentSerializer,
        responses={201: CourseEnrollmentSerializer(many=True)}
    )
    @action(detail=True, methods=['post'], url_path='assign-to-users')
    def assign_to_users(self, request, pk=None):
        """Assigner une formation à plusieurs utilisateurs"""
        course = self.get_object()
        serializer = CourseAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_ids = serializer.validated_data['user_ids']
        start_date = serializer.validated_data.get('start_date')
        end_date = serializer.validated_data.get('end_date')
        message = serializer.validated_data.get('message', '')

        # Vérifier que les utilisateurs existent
        from django.contrib.auth import get_user_model
        User = get_user_model()
        users = User.objects.filter(id__in=user_ids)
        if users.count() != len(user_ids):
            return Response(
                {'error': 'Un ou plusieurs utilisateurs n\'existent pas'},
                status=status.HTTP_400_BAD_REQUEST
            )

        enrollments = []
        created_count = 0
        updated_count = 0

        for user in users:
            enrollment, created = CourseEnrollment.objects.update_or_create(
                user=user,
                course=course,
                defaults={
                    'assigned_by': request.user,
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': message,
                    'status': CourseEnrollment.Status.ACTIVE,
                    'source': CourseEnrollment.Source.ORGANIZATION
                }
            )
            enrollments.append(enrollment)
            
            if created:
                created_count += 1
                # Créer une notification pour l'utilisateur
                from apps.organizations.models import UserNotification
                UserNotification.objects.create(
                    user=user,
                    type='training_assigned',
                    title=f"Nouvelle formation assignée : {course.title}",
                    message=f"Une formation '{course.title}' vous a été assignée. {message}",
                    related_training=course
                )
            else:
                updated_count += 1

        enrollment_serializer = CourseEnrollmentSerializer(enrollments, many=True)
        return Response({
            'created': created_count,
            'updated': updated_count,
            'enrollments': enrollment_serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def generate_certificate(self, request, pk=None):
        """Générer un certificat pour ce cours si terminé"""
        course = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)

        total_contents = Content.objects.filter(module__course=course).count()
        completed_contents = Progress.objects.filter(
            user=request.user,
            content__module__course=course,
            is_completed=True
        ).count()

        if total_contents == 0 or completed_contents < total_contents:
            return Response(
                {'detail': 'Vous devez terminer tous les contenus du cours pour obtenir un certificat'},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_quizzes = Quiz.objects.filter(module__course=course).count()
        completed_quizzes = QuizResult.objects.filter(
            user=request.user,
            quiz__module__course=course,
            score__gte=70,
        ).count()

        if total_quizzes == 0 or completed_quizzes < total_quizzes:
            return Response(
                {'detail': 'Vous devez terminer tous les quiz du cours pour obtenir un certificat'},
                status=status.HTTP_400_BAD_REQUEST
            )

        certificate, created = Certificate.objects.get_or_create(
            user=request.user,
            course=course
        )

        if created:
            return Response(
                CertificateSerializer(certificate, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {'detail': 'Certificat déjà généré pour ce cours'},
                status=status.HTTP_200_OK
            )


@extend_schema_view(
    list=extend_schema(
        summary="Liste des modules",
        description="Récupérer la liste des modules avec filtres",
        tags=["Modules"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un module",
        description="Récupérer les détails d'un module avec ses contenus",
        tags=["Modules"]
    ),
    create=extend_schema(
        summary="Créer un module",
        description="Créer un nouveau module",
        tags=["Modules"]
    ),
    update=extend_schema(
        summary="Mettre à jour un module",
        description="Mettre à jour complètement un module",
        tags=["Modules"]
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement un module",
        description="Mettre à jour partiellement un module",
        tags=["Modules"]
    ),
    destroy=extend_schema(
        summary="Supprimer un module",
        description="Supprimer définitivement un module",
        tags=["Modules"]
    )
)
class ModuleViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des modules"""
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ModuleFilter
    search_fields = ['title', 'description']
    ordering_fields = ['title']
    ordering = ['id']


@extend_schema_view(
    list=extend_schema(
        summary="Liste des contenus",
        description="Récupérer la liste des contenus avec filtres",
        tags=["Contenus"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un contenu",
        description="Récupérer les détails d'un contenu",
        tags=["Contenus"]
    ),
    create=extend_schema(
        summary="Créer un contenu",
        description="Créer un nouveau contenu",
        tags=["Contenus"]
    ),
    update=extend_schema(
        summary="Mettre à jour un contenu",
        description="Mettre à jour complètement un contenu",
        tags=["Contenus"]
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement un contenu",
        description="Mettre à jour partiellement un contenu",
        tags=["Contenus"]
    ),
    destroy=extend_schema(
        summary="Supprimer un contenu",
        description="Supprimer définitivement un contenu",
        tags=["Contenus"]
    )
)


class ContentViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des contenus"""
    queryset = Content.objects.select_related('module__course')
    serializer_class = ContentDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        if self.action in ['start', 'progress', 'mark_completed', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True, module__is_active=True, module__course__is_published=True)
        if self.request.user.is_staff:
            return queryset
        if not self.request.user.is_authenticated:
            return queryset.filter(is_preview=True)
        return queryset.filter(
            module__course__enrollments__user=self.request.user,
            module__course__enrollments__status=CourseEnrollment.Status.ACTIVE,
        ).distinct()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ContentFilter
    search_fields = ['title']
    ordering_fields = ['title', 'content_type']
    ordering = ['module__order', 'order', 'id']

    def get_serializer_class(self):
        if self.action == 'list':
            return ContentListSerializer
        else:
            return ContentDetailSerializer

    @extend_schema(
        summary="Démarrer un contenu",
        description="Enregistrer le début de lecture d'un contenu",
        tags=["Contenus"],
    )
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        content = self.get_object()
        enrollment = get_object_or_404(
            CourseEnrollment,
            user=request.user,
            course=content.module.course,
            status=CourseEnrollment.Status.ACTIVE,
        )
        progress, _ = Progress.objects.get_or_create(
            user=request.user,
            content=content,
            defaults={'enrollment': enrollment},
        )
        if not progress.started_at:
            progress.started_at = timezone.now()
            progress.save(update_fields=['started_at', 'updated_at'])
        return Response(ProgressSerializer(progress, context={'request': request}).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Mettre à jour la progression vidéo",
        description="Enregistrer la dernière position et la durée d'un contenu",
        tags=["Contenus"],
        request=ProgressUpdateSerializer,
    )
    @action(detail=True, methods=['patch'], url_path='progress')
    def progress(self, request, pk=None):
        content = self.get_object()
        serializer = ProgressUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment = get_object_or_404(
            CourseEnrollment,
            user=request.user,
            course=content.module.course,
            status=CourseEnrollment.Status.ACTIVE,
        )
        progress, _ = Progress.objects.get_or_create(
            user=request.user,
            content=content,
            defaults={'enrollment': enrollment},
        )
        progress.last_position_seconds = serializer.validated_data.get('last_position_seconds', progress.last_position_seconds)
        progress.duration_seconds = serializer.validated_data.get('duration_seconds') or progress.duration_seconds
        progress.save(update_fields=['last_position_seconds', 'duration_seconds', 'updated_at'])
        return Response(ProgressSerializer(progress, context={'request': request}).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Marquer comme terminé",
        description="Marquer ce contenu comme terminé pour l'utilisateur authentifié",
        tags=["Contenus"],
        responses={
            200: ProgressSerializer,
        }
    )
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Marquer ce contenu comme terminé"""
        content = self.get_object()
        enrollment = get_object_or_404(
            CourseEnrollment,
            user=request.user,
            course=content.module.course,
            status=CourseEnrollment.Status.ACTIVE,
        )
        result = complete_content(request.user, content, enrollment)
        return Response(result, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des quiz",
        description="Récupérer la liste des quiz avec filtres",
        tags=["Quiz"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un quiz",
        description="Récupérer les détails d'un quiz avec ses questions",
        tags=["Quiz"]
    ),
    create=extend_schema(
        summary="Créer un quiz",
        description="Créer un nouveau quiz",
        tags=["Quiz"]
    ),
    update=extend_schema(
        summary="Mettre à jour un quiz",
        description="Mettre à jour complètement un quiz",
        tags=["Quiz"]
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement un quiz",
        description="Mettre à jour partiellement un quiz",
        tags=["Quiz"]
    ),
    destroy=extend_schema(
        summary="Supprimer un quiz",
        description="Supprimer définitivement un quiz",
        tags=["Quiz"]
    )
)
class QuizViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des quiz"""
    queryset = Quiz.objects.select_related('module', 'module__course').prefetch_related('questions',
                                                                                        'questions__choices')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = QuizFilter
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at', 'passing_score']
    ordering = ['title']

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True, module__course__is_published=True)
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return queryset.filter(is_preview=True)
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(
            module__course__enrollments__user=self.request.user,
            module__course__enrollments__status=CourseEnrollment.Status.ACTIVE,
        ).distinct()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'list':
            return QuizListSerializer
        elif self.action in ['retrieve'] and not (self.request.user.is_staff or self.request.user.is_superuser):
            return QuizPublicSerializer
        return QuizSerializer

    @extend_schema(
        summary="Soumettre un quiz",
        description="Soumettre les réponses à un quiz complet",
        tags=["Quiz"],
        request=QuizSubmissionSerializer,
        responses={
            201: QuizResultSerializer,
        }
    )
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Soumettre les réponses à un quiz"""
        quiz = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)

        # Vérifier le nombre maximum de tentatives
        if quiz.max_attempts > 0:
            user_attempts = QuizResult.objects.filter(user=request.user, quiz_id=quiz.id).count()
            if user_attempts >= quiz.max_attempts:
                return Response(
                    {'detail': f'Nombre maximum de tentatives atteint ({quiz.max_attempts})'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = QuizSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        answers_data = serializer.validated_data['answers']

        # Vérifier que toutes les questions du quiz sont répondues
        quiz_questions = set(quiz.questions.values_list('id', flat=True))
        answered_questions = set(answer['question_id'] for answer in answers_data)

        if quiz_questions != answered_questions:
            return Response(
                {'detail': 'Toutes les questions doivent être répondues'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Récupérer la tentative en cours
            quiz_result = QuizResult.objects.filter(
                user=request.user,
                quiz=quiz,
                submitted_at__isnull=True
            ).order_by('-started_at').first()

            if not quiz_result:
                return Response(
                    {'detail': 'Aucune tentative de quiz en cours trouvée. Veuillez démarrer le quiz avant de le soumettre.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            quiz_result.submitted_at = timezone.now()

            total_points = 0
            obtained_points = 0

            for answer_data in answers_data:
                question_id = answer_data['question_id']
                choice_ids = answer_data['choice_ids']

                try:
                    question = quiz.questions.get(id=question_id)
                except QuizQuestion.DoesNotExist:
                    return Response(
                        {'detail': f'Question {question_id} non trouvée dans ce quiz'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                quiz_answer = QuizAnswer.objects.create(
                    result=quiz_result,
                    question=question
                )

                selected_choices = QuizChoice.objects.filter(
                    id__in=choice_ids,
                    question=question
                )

                if selected_choices.count() != len(choice_ids):
                    return Response(
                        {'detail': f'Choix invalides pour la question {question_id}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                quiz_answer.selected_choices.set(selected_choices)

                # Vérification de la correction
                correct_choices = question.choices.filter(is_correct=True)
                selected_correct = selected_choices.filter(is_correct=True)
                selected_incorrect = selected_choices.filter(is_correct=False)

                is_correct = (
                        selected_correct.count() == correct_choices.count() and
                        selected_incorrect.count() == 0
                )

                quiz_answer.is_correct = is_correct
                quiz_answer.points_earned = question.points if is_correct else 0
                quiz_answer.save()

                total_points += question.points
                obtained_points += quiz_answer.points_earned

            # Mise à jour du résultat final
            quiz_result.total_points = total_points
            quiz_result.obtained_points = obtained_points
            quiz_result.save()  # Le score et is_passed sont calculés automatiquement

        return Response(
            QuizResultSerializer(quiz_result, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Démarrer un quiz",
        description="Démarrer une nouvelle tentative de quiz",
        tags=["Quiz"],
        responses={201: QuizResultSerializer}
    )
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Démarrer une nouvelle tentative de quiz"""
        quiz = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)

        # Vérifier le nombre maximum de tentatives
        if quiz.max_attempts > 0:
            user_attempts = QuizResult.objects.filter(user=request.user, quiz_id=quiz.id).count()
            if user_attempts >= quiz.max_attempts:
                return Response(
                    {'detail': f'Nombre maximum de tentatives atteint ({quiz.max_attempts})'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Vérifier qu'il n'y a pas déjà une tentative en cours
        ongoing_attempt = QuizResult.objects.filter(
            user=request.user,
            quiz=quiz,
            submitted_at__isnull=True
        ).first()

        if ongoing_attempt:
            return Response(
                QuizResultSerializer(ongoing_attempt, context={'request': request}).data,
                status=status.HTTP_200_OK
            )

        # Créer une nouvelle tentative
        last_attempt = QuizResult.objects.filter(
            user=request.user, quiz=quiz
        ).order_by('-attempt_number').first()
        attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1

        quiz_result = QuizResult.objects.create(
            user=request.user,
            quiz=quiz,
            attempt_number=attempt_number
        )

        return Response(
            QuizResultSerializer(quiz_result, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    list=extend_schema(
        summary="Liste des résultats de quiz",
        description="Récupérer la liste des résultats de quiz de l'utilisateur",
        tags=["Quiz"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un résultat de quiz",
        description="Récupérer les détails d'un résultat de quiz",
        tags=["Quiz"]
    )
)
class QuizResultViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour la consultation des résultats de quiz"""
    serializer_class = QuizResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = QuizResultFilter
    ordering_fields = ['submitted_at', 'started_at', 'score', 'attempt_number']
    ordering = ['-started_at']

    def get_queryset(self):
        queryset = QuizResult.objects.select_related(
            'user', 'quiz', 'quiz__module', 'quiz__module__course'
        ).prefetch_related('answers', 'answers__selected_choices', 'answers__question')

        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return queryset.none()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return queryset
        return queryset.filter(user=self.request.user)

    @extend_schema(
        summary="Statistiques des quiz",
        description="Obtenir les statistiques de quiz pour l'utilisateur",
        tags=["Quiz"],
        responses={200: QuizStatsSerializer}
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques des résultats de quiz pour l'utilisateur"""
        queryset = self.get_queryset()

        if not request.user.is_staff:
            queryset = queryset.filter(user=request.user)

        total_attempts = queryset.count()
        total_quizzes = queryset.values('quiz').distinct().count()

        stats = queryset.aggregate(
            avg_score=Avg('score'),
            best_score=Max('score')
        )

        return Response({
            'total_attempts': total_attempts,
            'total_quizzes': total_quizzes,
            'average_score': round(stats['avg_score'] or 0, 2),
            'best_score': round(stats['best_score'] or 0, 2)
        })


@extend_schema_view(
    list=extend_schema(
        summary="Liste des progrès",
        description="Récupérer la liste des progrès de l'utilisateur",
        tags=["Progrès"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un progrès",
        description="Récupérer les détails d'un progrès",
        tags=["Progrès"]
    ),
    create=extend_schema(
        summary="Créer un progrès",
        description="Créer un nouveau progrès",
        tags=["Progrès"]
    ),
    update=extend_schema(
        summary="Mettre à jour un progrès",
        description="Mettre à jour complètement un progrès",
        tags=["Progrès"]
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement un progrès",
        description="Mettre à jour partiellement un progrès",
        tags=["Progrès"]
    ),
    destroy=extend_schema(
        summary="Supprimer un progrès",
        description="Supprimer définitivement un progrès",
        tags=["Progrès"]
    )
)
class ProgressViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des progrès"""
    serializer_class = ProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProgressFilter
    ordering_fields = ['completed_at']
    ordering = ['-completed_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Progress.objects.none()
        if self.request.user.is_staff:
            return Progress.objects.all()
        return Progress.objects.filter(user=self.request.user)

    @extend_schema(
        summary="Statistiques des progrès",
        description="Obtenir les statistiques de progrès pour l'utilisateur",
        tags=["Progrès"],
        responses={200: UserProgressStatsSerializer}
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques de progrès pour l'utilisateur"""
        queryset = self.get_queryset()

        if not request.user.is_staff:
            queryset = queryset.filter(user=request.user)

        total_contents = queryset.count()
        completed_contents = queryset.filter(is_completed=True).count()
        completion_rate = (completed_contents / total_contents * 100) if total_contents > 0 else 0

        return Response({
            'total_contents': total_contents,
            'completed_contents': completed_contents,
            'pending_contents': total_contents - completed_contents,
            'completion_rate': round(completion_rate, 2)
        })


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour la gestion des certificats"""
    serializer_class = CertificateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = CertificateFilter
    ordering_fields = ['issued_at', 'created_at']
    ordering = ['-created_at']
    lookup_field = 'pk'

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Certificate.objects.none()
        if self.request.user.is_staff:
            return Certificate.objects.all()
        return Certificate.objects.filter(user=self.request.user)

    def get_permissions(self):
        if self.action == 'verify':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @extend_schema(
        summary="Mes certificats",
        description="Liste des certificats de l'utilisateur connecté",
        tags=["Certificats"],
    )
    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        summary="Payer un certificat",
        description="Crée un paiement pour l'émission d'un certificat payant",
        tags=["Certificats"],
    )
    @action(detail=True, methods=['post'], url_path='checkout')
    def checkout(self, request, pk=None):
        certificate = self.get_object()
        if certificate.status == Certificate.Status.ISSUED:
            return Response({'code': 'CERTIFICATE_ALREADY_ISSUED', 'detail': 'Certificat déjà émis.'}, status=status.HTTP_400_BAD_REQUEST)
        if certificate.status == Certificate.Status.REVOKED:
            return Response({'code': 'CERTIFICATE_REVOKED', 'detail': 'Certificat révoqué.'}, status=status.HTTP_403_FORBIDDEN)
        if not certificate.payment_required or certificate.course.certificate_price <= 0:
            return Response({'code': 'PAYMENT_NOT_REQUIRED', 'detail': 'Le certificat est gratuit.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.payments.providers import PaymentProviderError, get_provider
        provider_name = request.data.get('provider', 'cinetpay')
        try:
            provider = get_provider(provider_name)
            checkout = provider.create_checkout(None, request.data.get('returnUrl', ''), request.data.get('cancelUrl', ''))
        except PaymentProviderError as e:
            return Response({'code': 'PAYMENT_PROVIDER_ERROR', 'detail': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payment = Payment.objects.create(
            user=request.user,
            purpose=Payment.Purpose.CERTIFICATE,
            certificate=certificate,
            course=certificate.course,
            amount=certificate.course.certificate_price,
            currency=certificate.course.currency,
            provider=provider_name,
            provider_reference=checkout['provider_reference'],
            checkout_url=checkout['checkout_url'],
        )
        certificate.status = Certificate.Status.PAYMENT_PENDING
        certificate.payment = payment
        certificate.save(update_fields=['status', 'payment', 'updated_at'])

        return Response({
            'payment_id': payment.id,
            'checkout_url': payment.checkout_url,
            'status': payment.status,
        })

    @extend_schema(
        summary="Émettre un certificat",
        description="Émet le certificat si les conditions sont remplies",
        tags=["Certificats"],
    )
    @action(detail=True, methods=['post'], url_path='issue')
    def issue(self, request, pk=None):
        certificate = self.get_object()
        if certificate.status == Certificate.Status.ISSUED:
            return Response(CertificateSerializer(certificate, context={'request': request}).data, status=status.HTTP_200_OK)
        if certificate.status == Certificate.Status.REVOKED:
            return Response({'code': 'CERTIFICATE_REVOKED', 'detail': 'Certificat révoqué.'}, status=status.HTTP_403_FORBIDDEN)

        if certificate.payment_required:
            payment = certificate.payment
            if not payment or payment.status != Payment.Status.SUCCEEDED:
                return Response({'code': 'CERTIFICATE_PAYMENT_REQUIRED', 'detail': 'Paiement requis avant émission.'}, status=status.HTTP_402_PAYMENT_REQUIRED)

        with transaction.atomic():
            certificate.status = Certificate.Status.ISSUED
            certificate.issued_at = timezone.now()
            certificate.participant_name_snapshot = request.user.get_full_name() or request.user.email
            certificate.course_title_snapshot = certificate.course.title
            certificate.level_snapshot = certificate.course.level
            certificate.duration_snapshot = str(certificate.course.estimated_duration or '')
            certificate.final_score = compute_course_progress(request.user, certificate.course, certificate.enrollment)['percentage']
            certificate.save(update_fields=['status', 'issued_at', 'participant_name_snapshot', 'course_title_snapshot', 'level_snapshot', 'duration_snapshot', 'final_score', 'updated_at'])

            if not certificate.pdf_file:
                from django.core.files.base import ContentFile
                pdf_bytes = generate_certificate_pdf(certificate)
                filename = f"certificate_{certificate.certificate_number}.pdf"
                certificate.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)

        return Response(CertificateSerializer(certificate, context={'request': request}).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Télécharger le certificat",
        description="Retourne une URL de téléchargement",
        tags=["Certificats"],
    )
    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        certificate = self.get_object()
        if certificate.status != Certificate.Status.ISSUED:
            return Response({'code': 'CERTIFICATE_NOT_ELIGIBLE', 'detail': 'Certificat non émis.'}, status=status.HTTP_403_FORBIDDEN)
        if not certificate.pdf_file:
            return Response({'code': 'PDF_NOT_READY', 'detail': 'PDF non généré.'}, status=status.HTTP_404_NOT_FOUND)
        from django.core.signing import TimestampSigner
        signer = TimestampSigner()
        token = signer.sign(f"cert:{certificate.id}")
        base = request.build_absolute_uri('/api/certificates/')
        return Response({
            'download_url': f"{base}{certificate.id}/download/?token={token}",
            'expires_at': timezone.now() + timezone.timedelta(seconds=300),
        })

    @extend_schema(
        summary="Vérifier un certificat",
        description="Page publique de vérification par code",
        tags=["Certificats"],
    )
    @action(detail=False, methods=['get'], url_path=r'verify/(?P<verification_code>[^/.]+)')
    def verify(self, request, verification_code=None):
        certificate = get_object_or_404(Certificate, verification_code=verification_code)
        if certificate.status == Certificate.Status.REVOKED:
            return Response({
                'valid': False,
                'status': 'revoked',
                'certificate_number': certificate.certificate_number,
                'revoked_at': certificate.revoked_at,
            })
        if certificate.status != Certificate.Status.ISSUED:
            return Response({'valid': False, 'status': certificate.status}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'valid': True,
            'status': 'issued',
            'certificate_number': certificate.certificate_number,
            'participant_name': certificate.participant_name_snapshot,
            'course_title': certificate.course_title_snapshot,
            'level': certificate.level_snapshot,
            'final_score': certificate.final_score,
            'issued_at': certificate.issued_at,
            'issuer': 'WIB Challenge',
        })


@extend_schema_view(
    tags=["Quiz"]
)
class QuizQuestionViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des questions de quiz"""
    queryset = QuizQuestion.objects.all()
    serializer_class = QuizQuestionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = QuizQuestionFilter
    search_fields = ['title', 'description']
    ordering_fields = ['title']
    ordering = ['id']


@extend_schema_view(
    list=extend_schema(
        summary="Liste des choix de réponse",
        description="Récupérer la liste des choix de réponse",
        tags=["Quiz"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un choix de réponse",
        description="Récupérer les détails d'un choix de réponse",
        tags=["Quiz"]
    ),
    create=extend_schema(
        summary="Créer un choix de réponse",
        description="Créer un nouveau choix de réponse",
        tags=["Quiz"]
    ),
    update=extend_schema(
        summary="Mettre à jour un choix de réponse",
        description="Mettre à jour complètement un choix de réponse",
        tags=["Quiz"]
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement un choix de réponse",
        description="Mettre à jour partiellement un choix de réponse",
        tags=["Quiz"]
    ),
    destroy=extend_schema(
        summary="Supprimer un choix de réponse",
        description="Supprimer définitivement un choix de réponse",
        tags=["Quiz"]
    )
)
class QuizChoiceViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des choix de réponse"""
    queryset = QuizChoice.objects.all()
    serializer_class = QuizChoiceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = QuizChoiceFilter
    search_fields = ['text']
    ordering_fields = ['text']
    ordering = ['id']


@extend_schema(
    tags=["Suggestion de cours"]
)
class CourseSuggestionView(generics.ListAPIView):
    serializer_class = CourseSuggestSerializer
    permission_classes = []  # [IsAuthenticated]
    queryset = Course.objects.all()

    @extend_schema(
        parameters=[
            OpenApiParameter('result', required=True, type=OpenApiTypes.INT)
        ],
        responses=CourseSerializer(many=True)
    )
    def get(self, request):
        """Obtenir des suggestions de cours"""
        serializer = self.get_serializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        courses = suggest_courses_from_attempt(
            get_object_or_404(
                SubmissionAttempt.objects.all(),
                pk=serializer.validated_data['result']
            )
        )
        return paginated_response(self, courses, CourseSerializer)
