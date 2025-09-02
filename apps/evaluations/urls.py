from django.urls import path, include
from rest_framework_nested import routers

from apps.evaluations.views import EvaluationViewSet, EvaluationSearchView
from apps.evaluations.views.candidates import CandidateEvaluationViewSet
from apps.evaluations.views.generated import GeneratePersonalityEvaluationView, GenerateEvaluationFromSpecsView
from apps.evaluations.views.participants import ParticipantViewSet
from apps.evaluations.views.questions import EvaluationQuestionsViewSet
from wib_challenge.routers import AppRouter

router = AppRouter()

router.register('evaluations', EvaluationViewSet, basename='evaluations')
router.register('evaluations/sessions', CandidateEvaluationViewSet, basename='attempts')
evaluation_router = routers.NestedDefaultRouter(router, 'evaluations', lookup='evaluation')

evaluation_router.register('questions', EvaluationQuestionsViewSet, basename='questions')
evaluation_router.register('participants', ParticipantViewSet, basename='participants')

urlpatterns = [
    path('evaluations/', EvaluationSearchView.as_view({'post': 'create', 'get': 'list'}), name='evaluation-search'),
    path('evaluations/builder/', GenerateEvaluationFromSpecsView.as_view(), name='generate-evaluation'),
    path('evaluations/personality-builder/', GeneratePersonalityEvaluationView.as_view(),
         name='generate-personality-evaluation'), path('', include(router.urls)),
    path('', include(evaluation_router.urls)), ]
