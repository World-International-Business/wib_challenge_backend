from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.core.views import ProfessionViewSet, TechnologyViewSet, DomainViewSet, ContactView

router = SimpleRouter()

router.register('domains', DomainViewSet, basename='domains')
router.register('professions', ProfessionViewSet, basename='professions')
router.register('technologies', TechnologyViewSet, basename='technologies')

urlpatterns = [
    path('contact/', ContactView.as_view(), name='contact'),
]

urlpatterns += router.urls
