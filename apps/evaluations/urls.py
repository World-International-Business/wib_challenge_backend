from django.urls import path, include
from rest_framework.routers import SimpleRouter
from rest_framework_nested import routers

from apps.evaluations.views import EvaluationViewSet
from apps.evaluations.views.candidates import CandidateEvaluationViewSet
from apps.evaluations.views.participants import ParticipantViewSet
from apps.evaluations.views.questions import EvaluationQuestionsViewSet

router = SimpleRouter()

router.register('evaluations', EvaluationViewSet, basename='evaluations')
router.register('evaluations/sessions', CandidateEvaluationViewSet, basename='attempts')
evaluation_router = routers.NestedSimpleRouter(router, 'evaluations', lookup='evaluation')

evaluation_router.register('questions', EvaluationQuestionsViewSet, basename='questions')
evaluation_router.register('participants', ParticipantViewSet, basename='participants')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(evaluation_router.urls))
]
