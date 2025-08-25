from django.urls import path

from apps.core.views import ProfessionViewSet, TechnologyViewSet, DomainViewSet, ContactView
from wib_challenge.routers import AppRouter

router = AppRouter()

router.register('domains', DomainViewSet, basename='domains')
router.register('professions', ProfessionViewSet, basename='professions')
router.register('technologies', TechnologyViewSet, basename='technologies')

urlpatterns = [
    path('contact/', ContactView.as_view(), name='contact'),
]

urlpatterns += router.urls
