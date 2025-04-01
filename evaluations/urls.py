from rest_framework.routers import SimpleRouter
from rest_framework_nested import routers

from evaluations.views import EvaluationViewSet
from questions.views import QuestionViewSet

router = SimpleRouter()

router.register('evaluations', EvaluationViewSet, basename='evaluations')

evaluation_router = routers.NestedSimpleRouter(router, 'evaluations', lookup='evaluation')

evaluation_router.register('questions', QuestionViewSet, basename='questions')

urlpatterns = [
    *router.urls,
    *evaluation_router.urls
]
