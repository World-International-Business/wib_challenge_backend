import json
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Technology
from apps.jobs.models import JobOffer, JobCategory, ExperienceLevel
from apps.organizations.models import Organization


# Données de test pour les offres d'emploi
JOB_OFFERS_DATA = [
    {
        "title": "Développeur Full Stack Python/Django",
        "category": "Développement Web",
        "skills": ["Python", "Django", "PostgreSQL", "React"],
        "job_type": "full_time",
        "experience_level": "mid",
        "location": "Paris, France",
        "remote_allowed": True,
        "salary": "45 000 - 65 000 €",
        "currency": "EUR",
        "description": "Nous recherchons un développeur Full Stack pour rejoindre notre équipe produit. Vous serez responsable du développement de nouvelles fonctionnalités et de l'amélioration de l'architecture existante.",
        "responsibilities": "- Développer et maintenir des applications web en Python/Django\n- Concevoir des APIs REST sécurisées\n- Collaborer avec les équipes frontend\n- Participer aux revues de code\n- Optimiser les performances",
        "requirements": "- 3+ ans d'expérience en Python/Django\n- Expérience avec les APIs REST\n- Maîtrise de PostgreSQL\n- Connaissance de React\n- Bon niveau anglais technique",
        "benefits": "- Télétravail hybride 2j/semaine\n- Mutuelle prise en charge à 80%\n- Tickets restaurant\n- Formation continue",
        "status": "published",
    },
    {
        "title": "Data Scientist Junior",
        "category": "Data Science",
        "skills": ["Python", "Pandas", "Scikit-learn", "TensorFlow", "SQL"],
        "job_type": "full_time",
        "experience_level": "junior",
        "location": "Lyon, France",
        "remote_allowed": True,
        "salary": "35 000 - 45 000 €",
        "currency": "EUR",
        "description": "Poste de Data Scientist junior pour analyser des données clients et construire des modèles de machine learning.",
        "responsibilities": "- Analyser les données clients\n- Construire des modèles ML\n- Créer des dashboards\n- Collaborer avec l'équipe data",
        "requirements": "- Master en Data Science ou équivalent\n- Python et bibliothèques data (Pandas, NumPy)\n- Première expérience en ML appréciée\n- SQL",
        "benefits": "- Équipe jeune et dynamique\n- Formation certifiante\n- Télétravail possible",
        "status": "published",
    },
    {
        "title": "DevOps Engineer AWS",
        "category": "DevOps",
        "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD"],
        "job_type": "full_time",
        "experience_level": "senior",
        "location": "Bordeaux, France",
        "remote_allowed": False,
        "salary": "55 000 - 75 000 €",
        "currency": "EUR",
        "description": "Ingénieur DevOps senior pour gérer notre infrastructure cloud et améliorer nos processus CI/CD.",
        "responsibilities": "- Maintenir et optimiser l'infrastructure AWS\n- Automatiser les déploiements\n- Gérer les pipelines CI/CD\n- Monitoring et alerting\n- Sécuriser l'infrastructure",
        "requirements": "- 5+ ans d'expérience DevOps\n- Expertise AWS (EC2, ECS, RDS, Lambda)\n- Docker et Kubernetes\n- Infrastructure as Code (Terraform)\n- Expérience CI/CD (GitLab CI ou GitHub Actions)",
        "benefits": "- Package attractif\n- Budget formation AWS\n- Journées de télétravail",
        "status": "published",
    },
    {
        "title": "QA Tester Junior",
        "category": "Qualité",
        "skills": ["Selenium", "Cypress", "JIRA", "SQL"],
        "job_type": "internship",
        "experience_level": "junior",
        "location": "Toulouse, France",
        "remote_allowed": True,
        "salary": "Stage rémunéré",
        "currency": "EUR",
        "description": "Stage de fin d'études en QA/testing pour notre équipe de développement.",
        "responsibilities": "- Tester les applications web\n- Écrire des cas de test\n- Signaler les bugs\n- Participer aux améliorations QA",
        "requirements": "- Étudiant en informatique ou équivalent\n- Connaissance de Selenium ou Cypress\n- Attentif aux détails\n- Bonne organisation",
        "benefits": "- Supervisé par des seniors\n- Participation à des projets réels\n- Possibilité d'embauche",
        "status": "published",
    },
]


class Command(BaseCommand):
    help = 'Seed job offers data'

    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Force seed even if data already exists')

    @transaction.atomic
    def handle(self, *args, **options):
        force = options.get('force', False)

        # Trouver ou créer une organisation "WIB Challenge"
        org, org_created = Organization.objects.get_or_create(
            name='WIB Challenge',
        )
        if org_created:
            self.stdout.write(self.style.SUCCESS('Created organization: WIB Challenge'))

        # Créer les catégories d'emploi si elles n'existent pas
        categories_created = 0
        for cat_name in ['Développement Web', 'Data Science', 'DevOps', 'Qualité']:
            cat, created = JobCategory.objects.get_or_create(title=cat_name)
            if created:
                categories_created += 1
        if categories_created:
            self.stdout.write(self.style.SUCCESS(f'Created {categories_created} job categories'))

        # Créer les offres d'emploi
        created_offers = 0
        for offer_data in JOB_OFFERS_DATA:
            title = offer_data['title']
            if JobOffer.objects.filter(title=title).exists():
                if force:
                    JobOffer.objects.filter(title=title).delete()
                else:
                    self.stdout.write(self.style.WARNING(f'Job offer "{title}" already exists'))
                    continue

            # Trouver la catégorie
            try:
                category = JobCategory.objects.get(title=offer_data['category'])
            except JobCategory.DoesNotExist:
                category = JobCategory.objects.create(title=offer_data['category'])

            # Trouver les compétences
            skills = Technology.objects.filter(name__in=offer_data['skills'])
            if not skills.exists():
                self.stdout.write(self.style.WARNING(
                    f'Skills not found for "{title}", creating them'))
                for skill_name in offer_data['skills']:
                    skills.create(name=skill_name)
                skills = Technology.objects.filter(name__in=offer_data['skills'])

            offer = JobOffer.objects.create(
                title=title,
                company=org,
                poste=category,
                description=offer_data['description'],
                responsibilities=offer_data.get('responsibilities', ''),
                requirements=offer_data['requirements'],
                benefits=offer_data.get('benefits', ''),
                salary=offer_data.get('salary'),
                currency=offer_data.get('currency', 'EUR'),
                job_type=offer_data['job_type'],
                experience_level=offer_data['experience_level'],
                location=offer_data['location'],
                remote_allowed=offer_data['remote_allowed'],
                status=JobOffer.Status.PUBLISHED,
                published_at=timezone.now(),
                featured=True,
            )
            offer.skills.set(skills)
            created_offers += 1
            self.stdout.write(self.style.SUCCESS(f'Created job offer: {title}'))

        self.stdout.write(self.style.SUCCESS(f'Created {created_offers} job offers'))
