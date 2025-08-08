from rest_framework.routers import SimpleRouter

from apps.questions.views import ReadOnlyQuestionViewSet

router = SimpleRouter()

router.register('questions', ReadOnlyQuestionViewSet, basename='questions')

urlpatterns = router.urls
