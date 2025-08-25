from django.urls import path, include

from apps.organizations.views import OrganizationViewSet
from wib_challenge.routers import AppRouter

router = AppRouter()

router.register(r'organizations', OrganizationViewSet, basename='organizations')

urlpatterns = [
    path('', include(router.urls)),
]
