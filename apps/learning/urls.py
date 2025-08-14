from rest_framework.routers import DefaultRouter
from .views import (
    CourseViewSet, ModuleViewSet, ContentViewSet, QuizViewSet, QuizQuestionViewSet, QuizChoiceViewSet,
    QuizResultViewSet, ProgressViewSet, CertificateViewSet
)

router = DefaultRouter()

router.register(r'courses', CourseViewSet, basename='course')
router.register(r'modules', ModuleViewSet, basename='module')
router.register(r'contents', ContentViewSet, basename='content')
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'quiz-questions', QuizQuestionViewSet, basename='quiz-question')
router.register(r'quiz-choices', QuizChoiceViewSet, basename='quiz-choice')
router.register(r'quiz-results', QuizResultViewSet, basename='quiz-result')
router.register(r'progress', ProgressViewSet, basename='progress')
router.register(r'certificates', CertificateViewSet, basename='certificate')

urlpatterns = router.urls
