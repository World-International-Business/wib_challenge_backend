from rest_framework.routers import SimpleRouter

from questions.views import QuestionViewSet

router = SimpleRouter()

router.register('questions', QuestionViewSet, basename='questions')

urlpatterns = router.urls
