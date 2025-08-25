from apps.questions.views import ReadOnlyQuestionViewSet
from wib_challenge.routers import AppRouter

router = AppRouter()

router.register('questions', ReadOnlyQuestionViewSet, basename='questions')

urlpatterns = router.urls
