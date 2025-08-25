from django.urls import path, include
from rest_framework_nested import routers

from apps.evaluations.views import EvaluationViewSet
from apps.evaluations.views.candidates import CandidateEvaluationViewSet
from apps.evaluations.views.generated import generate_personality_evaluation, generate_evaluation_from_specs
from apps.evaluations.views.participants import ParticipantViewSet
from apps.evaluations.views.questions import EvaluationQuestionsViewSet
from wib_challenge.routers import AppRouter

router = AppRouter()

router.register('evaluations', EvaluationViewSet, basename='evaluations')
router.register('evaluations/sessions', CandidateEvaluationViewSet, basename='attempts')
evaluation_router = routers.NestedSimpleRouter(router, 'evaluations', lookup='evaluation')

evaluation_router.register('questions', EvaluationQuestionsViewSet, basename='questions')
evaluation_router.register('participants', ParticipantViewSet, basename='participants')

urlpatterns = [
    path('evaluations/builder/', generate_evaluation_from_specs, name='generate-evaluation'),
    path('evaluations/personality-builder/', generate_personality_evaluation, name='generate-personality-evaluation'),
    path('', include(router.urls)),
    path('', include(evaluation_router.urls)),
]
