from django.urls import path

from .views import PaymentViewSet


urlpatterns = [
    path('course-checkout/', PaymentViewSet.as_view({'post': 'course_checkout'}), name='payment-course-checkout'),
    path('webhooks/<str:provider>/', PaymentViewSet.as_view({'post': 'webhooks'}), name='payment-webhook'),
    path('', PaymentViewSet.as_view({'get': 'list'}), name='payment-list'),
    path('<int:pk>/', PaymentViewSet.as_view({'get': 'retrieve'}), name='payment-detail'),
]
