from django.urls import path
from rest_framework_nested import routers

from organizations.views import OrganizationViewSet, OrgQuestionViewSet
from organizations.views.evaluations import generate_evaluation, OrgEvaluationViewSet
from organizations.views.candidate_evaluation import CandidateEvaluationView

router = routers.SimpleRouter()

router.register(r'organizations', OrganizationViewSet, basename='organizations')

organization_router = routers.NestedSimpleRouter(router, r'organizations', lookup='organization')

organization_router.register(r'evaluations', OrgEvaluationViewSet, basename='evaluations')

organization_router.register(r'questions', OrgQuestionViewSet, basename='questions')

router.register(r'organizations/invitations/(?P<token>[\w-]+)', CandidateEvaluationView, basename='candidate-evaluation')

urlpatterns = [
    path('organizations/evaluations/builder/', generate_evaluation, name='generate-evaluation'),
    *organization_router.urls,
    *router.urls,
]
