from decouple import config
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.evaluations.models import EvaluationInvitation




def send_reminder_email(request, invitation: EvaluationInvitation):
    publisher = invitation.evaluation.publisher
    context = {
        'candidate_name': invitation.candidate.full_name,
        'company_name': publisher.organization.name if hasattr(publisher,
                                                               'organization') else publisher.get_full_name(),
        'test_name': invitation.evaluation.title,
        'test_url': config('FRONTEND_INVITATION_URL', cast=str, default='').strip('/') + '/' + invitation.token,
        'unsubscribe_url': '',  # TODO : add unsubscribe url
        'privacy_url': '',  # TODO : add privacy url
        'current_year': timezone.now().year,
        'expire_at': invitation.expires_at,
        'logo_url': request.build_absolute_uri('/static/favicon.png'),
        'invited_at': invitation.invited_at,
    }

    html_message = render_to_string(
        'organizations/evaluation_reminder.html', context, request)

    text_message = render_to_string(
        'organizations/evaluation_reminder_text.txt', context, request)

    send_mail(
        'Rappel : Invitation à une évaluation technique',
        text_message,
        None,
        [invitation.candidate.email],
        html_message=html_message
    )
