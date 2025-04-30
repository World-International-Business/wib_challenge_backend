from decouple import config
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from organizations.models import EvaluationInvitation


def send_invitation_email(request, invitation: EvaluationInvitation):
    context = {
        'candidate_name': invitation.candidate.full_name,
        'company_name': invitation.evaluation.organization.name,
        'test_name': invitation.evaluation.title,
        'test_url': config('FRONTEND_INVITATION_URL', cast=str, default='').strip('/') + '/' + invitation.token,
        'unsubscribe_url': '',  # TODO : add unsubscribe url
        'privacy_url': '',  # TODO : add privacy url
        'current_year': timezone.now().year,
        'expire_at': invitation.expires_at
    }

    html_message = render_to_string(
        'organizations/evaluation_invitation.html', context, request)

    text_message = render_to_string(
        'organizations/evaluation_invitation_text.txt', context, request)

    send_mail(
        'Invitation à une évaluation technique',
        text_message,
        None,
        [invitation.candidate.email],
        html_message=html_message
    )
