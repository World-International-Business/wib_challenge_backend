from rest_framework.routers import SimpleRouter
from .views import (
    CourseViewSet, ModuleViewSet, ContentViewSet, QuizViewSet, QuizQuestionViewSet, QuizChoiceViewSet,
    QuizResultViewSet, ProgressViewSet, CertificateViewSet
)

router = SimpleRouter()

router.register('courses', CourseViewSet, basename='course')
router.register('modules', ModuleViewSet, basename='module')
router.register('contents', ContentViewSet, basename='content')
router.register('quizzes', QuizViewSet, basename='quiz')
router.register('quiz-questions', QuizQuestionViewSet, basename='quiz-question')
router.register('quiz-choices', QuizChoiceViewSet, basename='quiz-choice')
router.register('quiz-results', QuizResultViewSet, basename='quiz-result')
router.register('progress', ProgressViewSet, basename='progress')
router.register('certificates', CertificateViewSet, basename='certificate')

urlpatterns = router.urls
