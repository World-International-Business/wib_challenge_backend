from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .views import (
    JobCategoryViewSet, JobOfferViewSet,
    MyJobOffersView, JobSearchView
)

router = SimpleRouter()
router.register(r'categories', JobCategoryViewSet)
router.register(r'offers', JobOfferViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('my-offers/', MyJobOffersView.as_view(), name='my-job-offers'),
    path('search/', JobSearchView.as_view(), name='job-search'),
]
