from django.urls import path

from apps.jobs.agent_api import (
    AuditList, BookingCreateView, ConsentView, DashboardStats, DeletionRequestView,
    HumanReviewView, InterviewBookView, InterviewSlotsView, PrivacyRequestView,
    RequestOTPView, RetentionView, VerifyOTPView, OnboardingView,
)
from apps.jobs.conversation_api import (
    ConversationApprove, ConversationMessageCreate, ConversationMessageEdit,
    OfferConversationDetail, OfferConversationListCreate,
)


urlpatterns = [
    path('audit/', AuditList.as_view(), name='recruitment-audit'),
    path('agent/events/', AuditList.as_view(), name='agent-events'),
    path('compliance/consents/', ConsentView.as_view(), name='compliance-consents'),
    path('compliance/access-requests/', PrivacyRequestView.as_view(), name='compliance-access'),
    path('compliance/deletion-requests/', DeletionRequestView.as_view(), name='compliance-deletion'),
    path('compliance/retention-policy/', RetentionView.as_view(), name='compliance-retention'),
    path('jobs/applications/dashboard-stats/', DashboardStats.as_view(), name='application-dashboard-stats'),
    path('jobs/applications/<int:pk>/human-review/', HumanReviewView.as_view(), name='application-human-review'),
    path('jobs/applications/<int:pk>/onboarding/', OnboardingView.as_view(), name='application-onboarding'),
    path('jobs/applications/<int:pk>/interview-booking/', BookingCreateView.as_view(), name='create-interview-booking'),
    path('jobs/interview-slots/<str:token>/', InterviewSlotsView.as_view(), name='interview-slots'),
    path('jobs/interview-slots/<str:token>/book/', InterviewBookView.as_view(), name='interview-book'),
    path('jobs/interview-booking/<str:token>/', InterviewSlotsView.as_view(), name='interview-booking-alias'),
    path('jobs/interview-booking/<str:token>/book/', InterviewBookView.as_view(), name='interview-book-alias'),
    path('jobs/contract/<str:token>/request-otp/', RequestOTPView.as_view(), name='contract-request-otp'),
    path('jobs/contract/<str:token>/verify-otp/', VerifyOTPView.as_view(), name='contract-verify-otp'),
    path('jobs/offer-conversations/', OfferConversationListCreate.as_view(), name='offer-conversations'),
    path('jobs/offer-conversations/<int:pk>/', OfferConversationDetail.as_view(), name='offer-conversation-detail'),
    path('jobs/offer-conversations/<int:pk>/messages/', ConversationMessageCreate.as_view(), name='offer-conversation-messages'),
    path('jobs/offer-conversations/<int:pk>/messages/<int:message_id>/', ConversationMessageEdit.as_view(), name='offer-conversation-message-edit'),
    path('jobs/offer-conversations/<int:pk>/approve/', ConversationApprove.as_view(), name='offer-conversation-approve'),
]
