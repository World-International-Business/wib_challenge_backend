import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from education.models import AcademicClass, School, Subject


class Command(BaseCommand):
    help = 'Initialise idempotemment la structure scolaire depuis les variables d environnement.'

    @transaction.atomic
    def handle(self, *args, **options):
        school_name = os.getenv('EDUCATION_SCHOOL_NAME', '').strip()
        school_code = os.getenv('EDUCATION_SCHOOL_CODE', '').strip() or slugify(school_name)
        if not school_name:
            self.stdout.write('EDUCATION_SCHOOL_NAME absent : aucune structure scolaire créée.')
            return
        if not school_code:
            raise CommandError('EDUCATION_SCHOOL_CODE est obligatoire si le nom ne produit pas de code.')

        school, created = School.objects.update_or_create(
            code=school_code,
            defaults={'name': school_name, 'is_active': True},
        )
        self.stdout.write(f"Etablissement {'créé' if created else 'actualisé'} : {school.name}")

        academic_year = os.getenv('EDUCATION_ACADEMIC_YEAR', '').strip()
        classes = os.getenv('EDUCATION_CLASSES', '').strip()
        if classes:
            if not academic_year:
                raise CommandError('EDUCATION_ACADEMIC_YEAR est obligatoire avec EDUCATION_CLASSES.')
            for raw_class in classes.split(','):
                name = raw_class.strip()
                if name:
                    AcademicClass.objects.update_or_create(
                        school=school,
                        name=name,
                        academic_year=academic_year,
                        defaults={'level': name},
                    )

        subjects = os.getenv('EDUCATION_SUBJECTS', '').strip()
        for raw_subject in subjects.split(',') if subjects else []:
            name = raw_subject.strip()
            if name:
                Subject.objects.get_or_create(school=school, name=name)

        self.stdout.write(self.style.SUCCESS('Structure scolaire initialisée.'))
