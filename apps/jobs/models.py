from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TitleSlugDescriptionModel

from apps.core.models import BaseModel, Technology
from apps.evaluations.models import ExperienceLevel
from apps.organizations.models import Organization


class JobCategory(TitleSlugDescriptionModel):
    """
    Modèle représentant les catégories de postes (ex: Développement, Marketing, Finance).
    Permet de classer les offres d'emploi par domaine d'expertise.
    """
    title = models.CharField(_("Nom de la catégorie"), max_length=100)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("Catégorie d'emploi")
        verbose_name_plural = _("Catégories d'emploi")
        ordering = ['title']

    def __str__(self):
        return self.title


class JobOffer(TitleSlugDescriptionModel):
    """
    Modèle principal pour les offres d'emploi.
    Contient toutes les informations relatives à un poste proposé par une entreprise.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Brouillon')
        PUBLISHED = 'published', _('Publié')
        EXPIRED = 'expired', _('Expiré')
        FILLED = 'filled', _('Fermé')

    class JobType(models.TextChoices):
        FULL_TIME = 'full_time', _('Temps plein')
        PART_TIME = 'part_time', _('Temps partiel')
        CDI = 'cdi', _('CDI')
        CDD = 'cdd', _('CDD')
        INTERNSHIP = 'internship', _('Stage')
        REMOTE = 'remote', _('Télétravail')
        FREELANCE = 'freelance', _('Freelance')

    class RequiredDocumentType(models.TextChoices):
        CV = 'cv', _('CV/Curriculum Vitae')
        COVER_LETTER = 'cover_letter', _('Lettre de motivation')
        PORTFOLIO = 'portfolio', _('Portfolio')
        DIPLOMA = 'diploma', _('Diplôme')
        ID_CARD = 'id_card', _('Pièce d\'identité')
        WORK_PERMIT = 'work_permit', _('Permis de travail')
        RECOMMENDATION_LETTER = 'recommendation_letter', _('Lettre de recommandation')
        CERTIFICATE = 'certificate', _('Certificat professionnel')
        TRANSCRIPT = 'transcript', _('Relevé de notes')

    title = models.CharField(_("Titre du poste"), max_length=255)
    company = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='job_offers',
                                verbose_name=_("Entreprise"))
    poste = models.ForeignKey(JobCategory, on_delete=models.PROTECT, related_name='job_offers',
                             verbose_name=_("Poste"))
    description = models.TextField(_("Description du poste"))
    skills = models.ManyToManyField(Technology, verbose_name=_('Compétences'), related_name='jobs')
    responsibilities = models.TextField(_("Responsabilités"), blank=True)
    requirements = models.TextField(_("Prérequis"))
    benefits = models.TextField(_("Avantages"), blank=True)
    salary = models.CharField(_("Salaire"), max_length=255, blank=True, null=True)
    currency = models.CharField(_("Devise"), max_length=3, default='EUR')
    job_type = models.CharField(_("Type de contrat"), max_length=20, choices=JobType.choices)
    experience_level = models.CharField(_("Niveau d'expérience"), max_length=20, choices=ExperienceLevel.choices)
    location = models.CharField(_("Localisation"), max_length=255)
    remote_allowed = models.BooleanField(_("Télétravail autorisé"), default=False)
    application_url = models.URLField(_("URL de candidature"), blank=True)
    application_email = models.EmailField(_("Email pour candidature"), blank=True)
    attachments = models.ImageField(_("Image/Flyer"), upload_to='job_attachments/', blank=True, null=True)
    required_documents = models.JSONField(_("Documents requis"), default=list, blank=True)
    status = models.CharField(_("Statut"), max_length=20, choices=Status.choices, default=Status.DRAFT)
    featured = models.BooleanField(_("Mise en avant"), default=False)
    created_at = models.DateTimeField(_("Date de création"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Date de mise à jour"), auto_now=True)
    published_at = models.DateTimeField(_("Date de publication"), null=True, blank=True)
    expires_at = models.DateTimeField(_("Date d'expiration"), null=True, blank=True)

    technical_evaluation = models.ForeignKey(
        'evaluations.Evaluation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_offers_technical',
        verbose_name=_("Évaluation technique"),
    )
    psychotech_evaluation = models.ForeignKey(
        'evaluations.Evaluation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_offers_psychotech',
        verbose_name=_("Évaluation psychotechnique"),
    )
    personality_evaluation = models.ForeignKey(
        'evaluations.Evaluation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_offers_personality',
        verbose_name=_("Évaluation de personnalité"),
    )

    class Meta:
        verbose_name = _("Offre d'emploi")
        verbose_name_plural = _("Offres d'emploi")
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class JobApplication(BaseModel):
    """
    Modèle pour les applications d'emploi.
   """
    class ApplicationStatus(models.TextChoices):
        PENDING = 'pending', _('En attente')
        SHORTLISTED = 'shortlisted', _('Présélectionné')
        ACCEPTED = 'accepted', _('Retenu')
        REJECTED = 'rejected', _('Rejeté')
    
    class ApplicationSource(models.TextChoices):
        SPONTANEOUS = 'spontaneous', _('Candidature Spontanée')
        MATCHED = 'matched', _('Candidature Matchée')
        EMAIL = 'email', _('Candidature par Email')

    job_offer = models.ForeignKey(JobOffer, on_delete=models.CASCADE, related_name='applications',
                                  verbose_name=_("Offre d'emploi"))
    source = models.CharField(
        _("Source de la candidature"),
        max_length=20,
        choices=ApplicationSource.choices,
        default=ApplicationSource.SPONTANEOUS,
        help_text=_("Indique si la candidature est spontanée ou issue du système de matching")
    )

    applicant_name = models.CharField(_("Nom du candidat"), max_length=255)
    applicant_email = models.EmailField(_("Email du candidat"))
    resume = models.FileField(_("CV"), upload_to='resumes/', blank=True, null=True)
    cover_letter = models.TextField(_("Lettre de motivation"), blank=True)
    documents = models.JSONField(_("Documents additionnels"), default=dict, blank=True, 
                                help_text=_("Stocke les URLs des documents additionnels requis (portfolio, diplôme, etc.)"))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING
    )
    ai_analysis = models.TextField(_("Analyse IA du CV"), blank=True)
    ai_decision = models.BooleanField(_("Décision IA"), null=True, blank=True)

    is_matched = models.BooleanField(_("Matchée"), default=False)
    match_score = models.PositiveSmallIntegerField(_("Score de matching"), null=True, blank=True)

    submitted_at = models.DateTimeField(_("Date de soumission"), auto_now_add=True)
    
    # Champs pour le workflow de recrutement
    assigned_evaluation = models.ForeignKey('evaluations.Evaluation', on_delete=models.SET_NULL, 
                                           null=True, blank=True, related_name='applications',
                                           verbose_name=_("Évaluation assignée"))
    evaluation_score = models.DecimalField(_("Score de l'évaluation"), max_digits=5, decimal_places=2, 
                                          null=True, blank=True)
    interview_date = models.DateTimeField(_("Date de l'entretien"), null=True, blank=True)
    interview_duration = models.IntegerField(_("Durée de l'entretien (minutes)"), null=True, blank=True)
    interview_link = models.URLField(_("Lien de visioconférence"), blank=True)
    interview_type = models.CharField(_("Type d'entretien"), max_length=50, blank=True)
    interview_notes = models.TextField(_("Notes de l'entretien"), blank=True)
    recruitment_details = models.TextField(_("Détails de prise de poste"), blank=True)

    class ContractStatus(models.TextChoices):
        NOT_PREPARED = 'not_prepared', _('Non préparé')
        SENT = 'sent', _('Envoyé')
        SIGNED = 'signed', _('Signé')
        REJECTED = 'rejected', _('Refusé')
        EXPIRED = 'expired', _('Expiré')

    contract_status = models.CharField(
        _("Statut du contrat"),
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.NOT_PREPARED,
    )
    contract_file = models.FileField(_("Contrat (PDF)"), upload_to='contracts/', blank=True, null=True)
    signed_contract_file = models.FileField(_("Contrat signé (PDF)"), upload_to='contracts/signed/', blank=True, null=True)
    contract_token = models.CharField(_("Token contrat"), max_length=128, blank=True, default='', db_index=True)
    contract_token_expires_at = models.DateTimeField(_("Expiration token contrat"), null=True, blank=True)
    contract_sent_at = models.DateTimeField(_("Envoyé le"), null=True, blank=True)
    contract_signed_at = models.DateTimeField(_("Signé le"), null=True, blank=True)

    class Meta:
        verbose_name = _("Candidature")
        verbose_name_plural = _("Candidatures")
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.applicant_name} - {self.job_offer.title}"


class JobApplicationEvaluation(BaseModel):
    class Status(models.TextChoices):
        ASSIGNED = 'assigned', _('Assignée')
        STARTED = 'started', _('Commencée')
        COMPLETED = 'completed', _('Terminée')

    job_application = models.ForeignKey(
        JobApplication,
        on_delete=models.CASCADE,
        related_name='evaluations',
        verbose_name=_("Candidature"),
    )
    evaluation = models.ForeignKey(
        'evaluations.Evaluation',
        on_delete=models.CASCADE,
        related_name='job_application_evaluations',
        verbose_name=_("Évaluation"),
    )
    invitation = models.ForeignKey(
        'evaluations.EvaluationInvitation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_application_evaluations',
        verbose_name=_("Invitation"),
    )
    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED,
    )
    score = models.DecimalField(_("Score"), max_digits=6, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(_("Terminé le"), null=True, blank=True)

    class Meta:
        unique_together = (('job_application', 'evaluation'),)
        verbose_name = _("Évaluation de candidature")
        verbose_name_plural = _("Évaluations de candidatures")
        ordering = ['-created_at']


class JobApplicationAnalysis(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'pending', _('En attente')
        PROCESSING = 'processing', _('En cours')
        DONE = 'done', _('Terminé')
        FAILED = 'failed', _('Échec')

    class Provider(models.TextChoices):
        GEMINI = 'gemini', _('Gemini')
        LOCAL = 'local', _('Local')

    application = models.OneToOneField(
        JobApplication,
        on_delete=models.CASCADE,
        related_name='analysis',
        verbose_name=_('Candidature'),
    )

    status = models.CharField(
        _('Statut'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    provider = models.CharField(
        _('Provider'),
        max_length=20,
        choices=Provider.choices,
        null=True,
        blank=True,
    )

    extracted_data = models.JSONField(_('Données extraites'), default=dict, blank=True)
    analysis_markdown = models.TextField(_('Analyse (markdown)'), blank=True)
    decision = models.BooleanField(_('Décision'), null=True, blank=True)
    error = models.TextField(_('Erreur'), blank=True)

    started_at = models.DateTimeField(_('Début'), null=True, blank=True)
    finished_at = models.DateTimeField(_('Fin'), null=True, blank=True)

    class Meta:
        verbose_name = _('Analyse de candidature')
        verbose_name_plural = _('Analyses de candidatures')

    def __str__(self):
        return f"Analysis #{self.id} - application={self.application_id}"
