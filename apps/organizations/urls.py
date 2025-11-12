from django.urls import path, include

from apps.organizations.views import OrganizationViewSet, NotificationViewSet, UserNotificationViewSet
from wib_challenge.routers import AppRouter

router = AppRouter()

router.register(r'organizations', OrganizationViewSet, basename='organizations')
router.register(r'organizations/notifications', NotificationViewSet, basename='organization-notifications')
router.register(r'user-notifications', UserNotificationViewSet, basename='user-notifications')

urlpatterns = [
    path('', include(router.urls)),
]
