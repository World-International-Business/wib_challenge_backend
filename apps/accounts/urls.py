from django.urls import path, include
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenVerifyView, TokenBlacklistView, TokenRefreshView, TokenObtainPairView

from apps.accounts.views import RegisterUserView, UserViewSet, PasswordResetView, PasswordResetConfirmView, \
    GoogleLoginView
from wib_challenge.routers import AppRouter

users_router = AppRouter()

users_router.register(r'users', UserViewSet, basename='users')


def set_auth_tags(_class):
    return extend_schema(tags=["Authentification"])(_class)


token_verify = set_auth_tags(TokenVerifyView).as_view()
token_refresh = set_auth_tags(TokenRefreshView).as_view()
token_blacklist = set_auth_tags(TokenBlacklistView).as_view()
token_obtain_pair = set_auth_tags(TokenObtainPairView).as_view()

auth_urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),
    path('login/', token_obtain_pair, name='token_obtain_pair'),
    path('token/verify/', token_verify, name='token_verify'),
    path('token/refresh/', token_refresh, name='token_refresh'),
    path('forgot-password/', PasswordResetView.as_view(), name='password_reset'),
    path('reset-password/<str:uidb64>/<str:token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('logout/', token_blacklist, name='logout'),
    path('google/', GoogleLoginView.as_view(), name='google_login')
]

# oauth2_urlpatterns = [
#     path('google/', google_oauth2, name='google_oauth2')
# ]

urlpatterns = [
    path('', include(users_router.urls)),
    path('auth/', include(auth_urlpatterns)),
    # path('oauth2/', include(oauth2_urlpatterns))

]
