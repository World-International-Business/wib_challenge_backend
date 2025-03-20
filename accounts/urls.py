from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import token_obtain_pair, token_verify, token_refresh, token_blacklist

from accounts.views import RegisterUser, UserViewSet, PasswordResetView, PasswordResetConfirmView

users_router = DefaultRouter()

users_router.register(r'users', UserViewSet, basename='users')

auth_urlpatterns = [
    path('register/', RegisterUser.as_view(), name='register'),
    path('login/', token_obtain_pair, name='token_obtain_pair'),
    path('token/verify/', token_verify, name='token_verify'),
    path('token/refresh/', token_refresh, name='token_refresh'),
    path('forgot-password/', PasswordResetView.as_view(), name='password_reset'),
    path('reset-password/<str:uidb64>/<str:token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('logout/', token_blacklist, name='logout'),
]

urlpatterns = [
    path('', include(users_router.urls)),
    path('auth/', include(auth_urlpatterns))
]
