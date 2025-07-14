from django.db import transaction
from django.db.models import Avg, Max
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response

from .filters import (
    CourseFilter, ModuleFilter, ContentFilter, QuizFilter, QuizQuestionFilter, QuizChoiceFilter,
    QuizResultFilter, ProgressFilter, CertificateFilter
)
from .models import (
    Course, Module, Content, Quiz, QuizQuestion, QuizChoice, QuizAnswer, QuizResult,
    Progress, Certificate
)
from .serializers import (
    CourseSerializer, CourseListSerializer, ModuleSerializer, ContentDetailSerializer, ContentListSerializer,
    QuizSerializer, QuizPublicSerializer, QuizQuestionSerializer,
    QuizChoiceSerializer, QuizResultSerializer, ProgressSerializer, CertificateSerializer,
    CourseProgressSerializer, UserProgressStatsSerializer, QuizStatsSerializer,
    ErrorResponseSerializer, SuccessMessageSerializer, QuizSubmissionSerializer
)


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
            404: ErrorResponseSerializer
        }
    ),
    create=extend_schema(
        summary="Créer un cours",
        description="Créer un nouveau cours",
        tags=["Cours"],
        responses={
            201: CourseSerializer,
            400: ErrorResponseSerializer
        }
    ),
    update=extend_schema(
        summary="Mettre à jour un cours",
        description="Mettre à jour complètement un cours",
        tags=["Cours"],
        responses={
            200: CourseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer
        }
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement un cours",
        description="Mettre à jour partiellement un cours",
        tags=["Cours"],
        responses={
            200: CourseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer
        }
    ),
    destroy=extend_schema(
        summary="Supprimer un cours",
        description="Supprimer définitivement un cours",
        tags=["Cours"],
        responses={
            204: None,
            404: ErrorResponseSerializer
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

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        return CourseSerializer

    @extend_schema(
        summary="Progrès du cours",
        description="Obtenir le progrès de l'utilisateur authentifié pour ce cours",
        tags=["Cours"],
        responses={
            200: CourseProgressSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer
        }
    )
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Obtenir le progrès de l'utilisateur pour ce cours"""
        course = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)

        total_contents = Content.objects.filter(module__course=course).count()
        completed_contents = Progress.objects.filter(
            user=request.user,
            content__module__course=course,
            is_completed=True
        ).count()

        percentage = (completed_contents / total_contents * 100) if total_contents > 0 else 0

        return Response({
            'course_id': course.id,
            'total_contents': total_contents,
            'completed_contents': completed_contents,
            'percentage': round(percentage, 2),
            'is_completed': percentage == 100
        })

    @extend_schema(
        summary="Générer un certificat",
        description="Générer un certificat pour ce cours si l'utilisateur l'a terminé",
        tags=["Cours"],
        responses={
            200: SuccessMessageSerializer,
            201: CertificateSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer
        }
    )
    @action(detail=True, methods=['post'])
    def generate_certificate(self, request, pk=None):
        """Générer un certificat pour ce cours si terminé"""
        course = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)

        # Vérifier si le cours est terminé
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

        # Vérifier si le certificat existe déjà
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
    queryset = Content.objects.all()
    serializer_class = ContentDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ContentFilter
    search_fields = ['title']
    ordering_fields = ['title', 'content_type']
    ordering = ['id']

    def get_serializer_class(self):
        if self.action == 'list':
            return ContentListSerializer
        else:
            return ContentDetailSerializer

    @extend_schema(
        summary="Marquer comme terminé",
        description="Marquer ce contenu comme terminé pour l'utilisateur authentifié",
        tags=["Contenus"],
        responses={
            200: ProgressSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer
        }
    )
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Marquer ce contenu comme terminé"""
        content = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)

        progress, created = Progress.objects.get_or_create(
            user=request.user,
            content=content,
            defaults={'is_completed': True, 'completed_at': timezone.now()}
        )

        if not created and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save()

        return Response(
            ProgressSerializer(progress, context={'request': request}).data,
            status=status.HTTP_200_OK
        )


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
    queryset = Quiz.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = QuizFilter
    search_fields = ['title', 'description']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve'] and not self.request.user.is_staff:
            return QuizPublicSerializer
        return QuizSerializer

    @extend_schema(
        summary="Soumettre un quiz",
        description="Soumettre les réponses à un quiz complet",
        tags=["Quiz"],
        request=QuizSubmissionSerializer,
        responses={
            201: QuizResultSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer
        }
    )
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Soumettre les réponses à un quiz"""
        quiz = self.get_object()
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = QuizSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        answers_data = serializer.validated_data['answers']

        with transaction.atomic():
            # Créer le résultat de quiz
            quiz_result = QuizResult.objects.create(
                user=request.user,
                quiz=quiz,
                score=0  # Sera calculé ci-dessous
            )

            total_questions = quiz.questions.count()
            correct_answers = 0

            # Traiter chaque réponse
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

                # Créer la réponse
                quiz_answer = QuizAnswer.objects.create(
                    result=quiz_result,
                    question=question,
                    is_correct=False  # Sera mis à jour ci-dessous
                )

                # Ajouter les choix sélectionnés
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

                # Vérifier si la réponse est correcte
                correct_choices = question.choices.filter(is_correct=True)
                selected_correct = selected_choices.filter(is_correct=True)
                selected_incorrect = selected_choices.filter(is_correct=False)

                # La réponse est correcte si tous les choix corrects sont sélectionnés
                # et aucun choix incorrect n'est sélectionné
                if (selected_correct.count() == correct_choices.count() and
                        selected_incorrect.count() == 0):
                    quiz_answer.is_correct = True
                    correct_answers += 1

                quiz_answer.save()

            # Calculer et sauvegarder le score
            score = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            quiz_result.score = score
            quiz_result.save()

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
    ordering_fields = ['submitted_at', 'score']
    ordering = ['-submitted_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return QuizResult.objects.all()
        return QuizResult.objects.filter(user=self.request.user)

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


@extend_schema_view(
    list=extend_schema(
        summary="Liste des certificats",
        description="Récupérer la liste des certificats de l'utilisateur",
        tags=["Certificats"]
    ),
    retrieve=extend_schema(
        summary="Détails d'un certificat",
        description="Récupérer les détails d'un certificat",
        tags=["Certificats"]
    )
)
class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour la consultation des certificats"""
    serializer_class = CertificateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = CertificateFilter
    ordering_fields = ['issued_at']
    ordering = ['-issued_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return Certificate.objects.all()
        return Certificate.objects.filter(user=self.request.user)


# ViewSets supplémentaires pour les questions et choix de quiz
@extend_schema_view(
    list=extend_schema(
        summary="Liste des questions de quiz",
        description="Récupérer la liste des questions de quiz",
        tags=["Quiz"]
    ),
    retrieve=extend_schema(
        summary="Détails d'une question de quiz",
        description="Récupérer les détails d'une question de quiz",
        tags=["Quiz"]
    ),
    create=extend_schema(
        summary="Créer une question de quiz",
        description="Créer une nouvelle question de quiz",
        tags=["Quiz"]
    ),
    update=extend_schema(
        summary="Mettre à jour une question de quiz",
        description="Mettre à jour complètement une question de quiz",
        tags=["Quiz"]
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement une question de quiz",
        description="Mettre à jour partiellement une question de quiz",
        tags=["Quiz"]
    ),
    destroy=extend_schema(
        summary="Supprimer une question de quiz",
        description="Supprimer définitivement une question de quiz",
        tags=["Quiz"]
    )
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
