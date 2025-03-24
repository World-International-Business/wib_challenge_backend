from rest_framework.routers import SimpleRouter

from core.views import ProfessionViewSet, TechnologyViewSet

router = SimpleRouter()

router.register('professions', ProfessionViewSet, basename='professions')
router.register('technologies', TechnologyViewSet, basename='technologies')

urlpatterns = router.urls
