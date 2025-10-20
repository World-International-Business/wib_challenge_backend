from django.urls import path, include

from wib_challenge.routers import AppRouter
from .views import (
    JobCategoryViewSet, JobOfferViewSet,
    MyJobOffersView, JobSearchView, JobApplicationViewSet, JobMatchView, JobMetadataView
)

router = AppRouter()
router.register(r'categories', JobCategoryViewSet)
router.register(r'offers', JobOfferViewSet)
router.register(r'applications', JobApplicationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('metadata/', JobMetadataView.as_view(), name='job-metadata'),
    path('my-offers/', MyJobOffersView.as_view(), name='my-job-offers'),
    path('search/', JobSearchView.as_view(), name='job-search'),
    path('match/', JobMatchView.as_view(), name='job-match'),
]
