from rest_framework.routers import SimpleRouter

from core.views import ProfessionViewSet, TechnologyViewSet, DomainViewSet

router = SimpleRouter()

router.register('domains', DomainViewSet, basename='domains')
router.register('professions', ProfessionViewSet, basename='professions')
router.register('technologies', TechnologyViewSet, basename='technologies')

urlpatterns = router.urls
