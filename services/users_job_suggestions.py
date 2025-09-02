from django.db.models import Count, Q, Avg, F, Case, When, Value, FloatField, ExpressionWrapper, OuterRef, Subquery, \
    Sum, QuerySet

from apps.accounts.models import User
from apps.evaluations.models import Evaluation, EvaluationType
from apps.jobs.models import JobOffer
from apps.questions.models import Question


def get_users_suggestions_for_job(job: JobOffer) -> QuerySet[User]:
    """
    Retourne un queryset d'utilisateurs qui correspondent à l'offre d'emploi.
    La correspondance est basée sur les critères suivants:
    - L'utilisateur doit avoir le rôle 'developer'
    - L'utilisateur doit être actif
    - L'utilisateur doit avoir un profil candidat
    - Le candidat doit être en recherche d'emploi (open_to_work=True)
    - Le candidat doit avoir au moins une des compétences requises pour le poste
    - Le candidat doit avoir un niveau d'expérience suffisant
    - Le candidat a un score d'au moins 55% aux évaluations liées aux compétences requises (si applicable)

    Les résultats sont triés par:
    1. Nombre de compétences correspondantes (décroissant)
    2. Score moyen des évaluations pertinentes (décroissant)
    3. Années d'expérience (décroissant)

    Args:
        job: L'offre d'emploi pour laquelle suggérer des candidats

    Returns:
        QuerySet: Un queryset d'utilisateurs qui correspondent à l'offre d'emploi
    """
    # Récupérer les compétences requises pour le poste
    required_skills = job.skills.all()

    # Filtrer les utilisateurs qui sont des développeurs actifs
    users = User.objects.filter(
        role=User.Roles.USER,
        is_active=True
    ).select_related('profile')

    # Filtrer les utilisateurs qui ont un profil candidat en recherche d'emploi
    users = users.filter(profile__isnull=False, profile__open_to_work=True)

    # Si l'offre spécifie un niveau d'expérience, filtrer les candidats en conséquence
    if job.experience_level:
        # Mapping simple des niveaux d'expérience vers des années d'expérience minimales
        experience_levels = {
            'entry': 0,
            'junior': 1,
            'mid': 3,
            'senior': 5,
            'expert': 8
        }
        min_experience = experience_levels.get(job.experience_level.lower(), 0)
        users = users.filter(profile__years_experience__gte=min_experience)

    # Précharger les technologies pour optimiser
    users = users.prefetch_related('profile__technologies')

    # Filtrer les utilisateurs qui ont au moins une des compétences requises
    if required_skills.exists():
        users = users.filter(profile__technologies__in=required_skills).distinct()

    # Annoter avec le nombre de compétences correspondantes
    users = users.annotate(
        matching_skills_count=Count(
            'profile__technologies',
            filter=Q(profile__technologies__in=required_skills)
        )
    )

    # Calculer les évaluations pertinentes pour le poste
    relevant_evaluations = Evaluation.objects.filter(
        evaluation_type=EvaluationType.TECHNICAL,
        technology__in=required_skills
    )

    if relevant_evaluations.exists():
        # Calculer le score maximum pour chaque évaluation en utilisant le champ weight
        evaluations_with_max_score = Evaluation.objects.filter(
            id=OuterRef('participant__attempts__evaluation_id')
        ).annotate(
            total_weight=Sum('questions__weight', filter=Q(questions__status=Question.Status.PUBLISHED))
        ).values('total_weight')[:1]

        # Utiliser le champ weight stocké pour calculer le pourcentage
        users = users.annotate(
            avg_score=Avg(
                Case(
                    When(
                        Q(participant__attempts__submission__isnull=False) &
                        Q(participant__attempts__evaluation__in=relevant_evaluations),
                        then=ExpressionWrapper(
                            100 * F('participant__attempts__submission__score') / Subquery(evaluations_with_max_score),
                            output_field=FloatField()
                        )
                    ),
                    default=Value(0),
                    output_field=FloatField()
                )
            )
        )

        # Filtrer uniquement les utilisateurs avec un score moyen >= 55%
        users = users.filter(avg_score__gte=55)

        # Trier par nombre de compétences, score d'évaluation et expérience
        return users.order_by('-matching_skills_count', '-avg_score', '-profile__years_experience')

    # Trier par nombre de compétences correspondantes et années d'expérience
    return users.order_by('-matching_skills_count', '-profile__years_experience')
