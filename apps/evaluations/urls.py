from rest_framework.routers import SimpleRouter
from rest_framework_nested import routers

from apps.evaluations.views import EvaluationViewSet, CandidateViewSet, SubmissionAttemptViewSet

router = SimpleRouter()

router.register('evaluations', EvaluationViewSet, basename='evaluations')
router.register('candidates', CandidateViewSet, basename='candidates')
router.register('attempts', SubmissionAttemptViewSet, basename='attempts')

evaluation_router = routers.NestedSimpleRouter(router, 'evaluations', lookup='evaluation')

urlpatterns = [
    *router.urls,
    *evaluation_router.urls
]
