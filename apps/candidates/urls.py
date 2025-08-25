from django.urls import include, path
from rest_framework_nested import routers

from apps.candidates.views import (
    CandidateProfileViewSet, ExperienceViewSet, LanguageViewSet, EducationViewSet,
    ProjectViewSet, ProjectImageViewSet, ProfileTechnologyViewSet
)
from wib_challenge.routers import AppRouter

router = AppRouter()

router.register(r'candidate-profiles', CandidateProfileViewSet, basename='candidates')

router.register(r'project-images', ProjectImageViewSet, basename='projects-images')

profile_router = routers.NestedSimpleRouter(router, r'candidate-profiles', lookup='profile')

profile_router.register(r'experiences', ExperienceViewSet, basename='experiences')

profile_router.register(r'technologies', ProfileTechnologyViewSet, basename='technologies')

profile_router.register(r'educations', EducationViewSet, basename='educations')

profile_router.register(r'languages', LanguageViewSet, basename='languages')

profile_router.register(r'projects', ProjectViewSet, basename='projects')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(profile_router.urls)),
]
