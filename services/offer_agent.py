import datetime
import logging

from django.conf import settings
from django.utils import timezone
from decouple import UndefinedValueError
from google.genai.errors import APIError
from google.genai.types import GenerateContentConfigDict
from httpx import RequestError, TimeoutException
from pydantic import BaseModel, Field, ValidationError

from apps.jobs.models import JobCategory, JobOffer, OfferConversation, ConversationMessage
from services.utils import get_genai_client

logger = logging.getLogger(__name__)

OFFER_AGENT_MODEL = 'gemini-3.5-flash-lite'

JOB_TYPES = [choice for choice, _ in JobOffer.JobType.choices]
EXPERIENCE_LEVELS = ['junior', 'intermediate', 'senior']
DOCUMENT_TYPES = [choice for choice, _ in JobOffer.RequiredDocumentType.choices]


class OfferAgentError(Exception):
    def __init__(self, code, message, status_code=502):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class JobCard(BaseModel):
    title: str
    poste: str = Field(description="Intitulé exact d'une catégorie existante, ou nouvelle catégorie courte si aucune ne convient")
    description: str
    responsibilities: str
    requirements: str
    benefits: str
    skills: list[str] = Field(description='Technologies/compétences, deux mots max chacune')
    job_type: str = Field(description=f'Un parmi : {", ".join(JOB_TYPES)}')
    experience_level: str = Field(description=f'Un parmi : {", ".join(EXPERIENCE_LEVELS)}')
    location: str
    remote_allowed: bool
    salary: str = Field(description='Fourchette salariale ou montant, texte court')
    currency: str = Field(description='Code devise ISO 4217, ex. XAF, EUR')
    application_instructions: str = Field(description='Consignes de candidature : email, lien, documents à joindre')
    required_documents: list[str] = Field(description=f'Documents exigés, parmi : {", ".join(DOCUMENT_TYPES)}')
    expires_at: str = Field(description="Date d'expiration au format YYYY-MM-DD")


class AgentReply(BaseModel):
    reply: str = Field(description='Texte adressé au recruteur : réponse, questions de clarification ou présentation de la fiche')
    questions: list[str] = Field(default_factory=list, description='Questions de clarification, 0 à 2 max, uniquement si un champ critique manque ou est ambigu')
    quick_replies: list[str] = Field(default_factory=list, description="Courtes réponses suggérées que le recruteur peut cliquer")
    job_card: JobCard | None = Field(default=None, description='Fiche de poste complète, uniquement quand le besoin est suffisamment précis')
    ready_to_publish: bool = Field(default=False, description='True quand la fiche est complète et présentée pour validation')


_SYSTEM_PROMPT = """\
Tu es un assistant RH conversationnel chargé d'aider un recruteur de {company} ({country})
à formuler son besoin de recrutement puis à obtenir une fiche de poste complète.

Règles de conduite :
- Réponds en français, de façon concise et professionnelle.
- Tu ne reformules pas mécaniquement : tu déduis le besoin, tu signales les incohérences.
- Si des informations CRITIQUES manquent (intitulé du poste, type de contrat, lieu,
  niveau attendu), pose au maximum 1 à 2 questions dans `questions` ET reformule-les
  naturellement dans `reply`. N'interroge jamais sur tout à la fois.
- Si le besoin est suffisamment clair, génère `job_card` COMPLET : aucun champ vide,
  aucun champ null. Déduis des valeurs raisonnables pour les champs non précisés
  (salaire adapté au marché de {country}, currency adaptée, expires_at = {default_expiry}
  par défaut, application_instructions = dépôt CV sur la plateforme sauf précision
  contraire, required_documents = ["cv"] par défaut).
- Pour `poste`, choisis en priorité un intitulé EXACT parmi les catégories existantes :
  {categories}
- `quick_replies` : 0 à 3 réponses courtes et naturelles que le recruteur pourrait cliquer
  (ex. "Oui", "Plutôt senior", "Télétravail possible"). Vide si inutile.
- `ready_to_publish` = true uniquement quand la fiche est complète et cohérente.
- Le contenu `reply` est affiché tel quel ; le markdown léger (gras, listes) est accepté.
"""


def _default_expiry() -> str:
    return (timezone.localdate() + datetime.timedelta(days=30)).isoformat()


def _history_text(conversation: OfferConversation) -> str:
    lines = []
    for message in conversation.messages.all():
        speaker = {'user': 'Recruteur', 'assistant': 'Assistant', 'system': 'Système'}[message.role]
        lines.append(f'{speaker}: {message.content}')
    return '\n'.join(lines)


def _normalize_job_card(card: JobCard) -> dict:
    data = card.model_dump()
    data['job_type'] = data['job_type'] if data['job_type'] in JOB_TYPES else 'full_time'
    data['experience_level'] = data['experience_level'] if data['experience_level'] in EXPERIENCE_LEVELS else 'intermediate'
    data['required_documents'] = [doc for doc in data['required_documents'] if doc in DOCUMENT_TYPES] or ['cv']
    try:
        expires = datetime.date.fromisoformat(data['expires_at'][:10])
    except (ValueError, TypeError):
        expires = timezone.localdate() + datetime.timedelta(days=30)
    data['expires_at'] = expires.isoformat()
    category, _ = JobCategory.objects.get_or_create(title=data['poste'].strip()[:100])
    data['poste_id'] = category.pk
    data['poste_title'] = category.title
    return data


def build_assistant_blocks(reply: AgentReply, organization) -> tuple[list[dict], dict | None]:
    blocks = [{'type': 'text', 'content': reply.reply}]
    draft = None
    if reply.job_card is not None:
        draft = _normalize_job_card(reply.job_card)
        card_data = {
            'title': draft['title'],
            'description': draft['description'],
            'responsibilities': draft['responsibilities'],
            'requirements': draft['requirements'],
            'benefits': draft['benefits'],
            'skills': draft['skills'],
            'jobType': draft['job_type'],
            'experienceLevel': draft['experience_level'],
            'location': draft['location'],
            'remoteAllowed': draft['remote_allowed'],
            'salary': draft['salary'],
            'currency': draft['currency'],
            'applicationInstructions': draft['application_instructions'],
            'requiredDocuments': draft['required_documents'],
            'poste': draft['poste_id'],
            'posteTitle': draft['poste_title'],
            'expiresAt': draft['expires_at'],
        }
        blocks.append({'type': 'job_card', 'data': card_data})
    if reply.quick_replies:
        blocks.append({'type': 'quick_replies', 'options': reply.quick_replies})
    return blocks, draft


def _next_state(reply: AgentReply) -> str:
    if reply.job_card is not None:
        return OfferConversation.State.REVIEW
    if reply.questions:
        return OfferConversation.State.CLARIFYING
    return OfferConversation.State.COLLECTING


def run_offer_agent(conversation: OfferConversation) -> ConversationMessage:
    """Exécute l'agent sur l'historique complet et persiste le message assistant."""
    organization = conversation.organization
    categories = ', '.join(JobCategory.objects.order_by('title').values_list('title', flat=True)) or 'aucune'
    system = _SYSTEM_PROMPT.format(
        company=organization.name, country=organization.country or 'Cameroun',
        categories=categories, default_expiry=_default_expiry())
    prompt = f"{system}\n\nConversation :\n{_history_text(conversation)}\n\nRéponds au dernier message du recruteur."
    try:
        client = get_genai_client()
    except (UndefinedValueError, ValueError) as exc:
        raise OfferAgentError('ai_not_configured', 'Le service IA n’est pas configuré.', 503) from exc
    try:
        response = client.models.generate_content(
            model=OFFER_AGENT_MODEL,
            contents=[prompt],
            config=GenerateContentConfigDict(response_schema=AgentReply, response_mime_type='application/json'),
        )
    except APIError as exc:
        if exc.code == 404:
            raise OfferAgentError('ai_model_unavailable', 'Le modèle IA est indisponible.', 503) from exc
        if exc.code in (401, 403):
            raise OfferAgentError('ai_authentication_failed', 'Le fournisseur IA refuse l’accès.', 503) from exc
        if exc.code == 429:
            raise OfferAgentError('ai_rate_limited', 'Quota IA atteint. Réessayez ultérieurement.', 429) from exc
        if exc.code and exc.code >= 500:
            raise OfferAgentError('ai_provider_unavailable', 'Le fournisseur IA est temporairement indisponible.', 503) from exc
        raise OfferAgentError('ai_request_rejected', 'Le fournisseur IA n’a pas pu traiter la demande.') from exc
    except (TimeoutException, TimeoutError) as exc:
        raise OfferAgentError('ai_timeout', 'Le fournisseur IA n’a pas répondu à temps.', 504) from exc
    except RequestError as exc:
        raise OfferAgentError('ai_connection_failed', 'Impossible de joindre le fournisseur IA.', 503) from exc
    try:
        reply = AgentReply.model_validate(response.parsed) if response.parsed is not None else \
            AgentReply.model_validate_json(response.text or '')
    except (ValidationError, ValueError, TypeError, AttributeError) as exc:
        raise OfferAgentError('ai_invalid_response', 'Réponse IA inexploitable. Réessayez.') from exc
    reply.questions = reply.questions[:2]
    reply.quick_replies = reply.quick_replies[:3]
    blocks, draft = build_assistant_blocks(reply, organization)
    message = ConversationMessage.objects.create(
        conversation=conversation, role=ConversationMessage.Role.ASSISTANT,
        content=reply.reply, blocks=blocks)
    conversation.state = _next_state(reply)
    if draft is not None:
        conversation.draft = draft
    if not conversation.title and draft:
        conversation.title = draft['title'][:200]
    elif not conversation.title:
        last_user = conversation.messages.filter(role=ConversationMessage.Role.USER).last()
        conversation.title = (last_user.content[:60] + '…') if last_user and len(last_user.content) > 60 else (last_user.content if last_user else '')
    conversation.save(update_fields=['state', 'draft', 'title', 'updated_at'])
    return message


def publish_conversation_offer(conversation: OfferConversation) -> JobOffer:
    """Crée le JobOffer final à partir du brouillon validé."""
    draft = conversation.draft or {}
    if not draft or 'poste_id' not in draft:
        raise OfferAgentError('draft_missing', 'Aucune fiche de poste n’a encore été générée dans cette conversation.', 409)
    if conversation.job_offer_id:
        return conversation.job_offer
    expires = None
    try:
        expires = datetime.date.fromisoformat(str(draft['expires_at'])[:10])
        expires = timezone.make_aware(datetime.datetime.combine(expires, datetime.time.max))
    except (ValueError, TypeError):
        pass
    offer = JobOffer.objects.create(
        title=draft['title'][:255],
        company=conversation.organization,
        poste_id=draft['poste_id'],
        description=draft['description'],
        responsibilities=draft['responsibilities'],
        requirements=draft['requirements'],
        benefits=draft['benefits'],
        salary=draft['salary'][:255],
        currency=draft['currency'][:3].upper(),
        job_type=draft['job_type'],
        experience_level=draft['experience_level'],
        location=draft['location'][:255],
        remote_allowed=draft['remote_allowed'],
        required_documents=draft['required_documents'],
        status=JobOffer.Status.DRAFT,
        expires_at=expires,
    )
    from apps.core.models import Technology
    wanted = [name.strip()[:255] for name in draft.get('skills', []) if name.strip()]
    offer.skills.set(Technology.objects.filter(name__in=wanted))
    conversation.job_offer = offer
    conversation.state = OfferConversation.State.APPROVED
    conversation.save(update_fields=['job_offer', 'state', 'updated_at'])
    return offer
