import json
from pathlib import Path
from random import shuffle
from django.core.management import BaseCommand, call_command
from django.db import transaction

from accounts.models import User
from core.models import Technology
from evaluations.models import Evaluation
from questions.models import Question, Choice


class Command(BaseCommand):
    help = 'Seed Evaluations data'

    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Force seed even if data already exists')

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = Path(__file__).resolve().parent / 'data'
        force = options.get('force', False)

        call_command('create_default_admin')

        admin_user = User.objects.get(pk=1)

        for file in data_dir.glob('*.json'):
            self.import_from_json(file, admin_user, force)

    def import_from_json(self, data_file: Path, admin_user: User, force=False):

        with data_file.open(encoding='utf-8') as f:
            data = json.load(f)
            tech_name = data.pop('technology')
            try:
                tech = Technology.objects.get(
                    name__iexact=tech_name)
            except Technology.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'Technology "{tech_name}" not found. Skipping file {data_file.name}.'))
                return
            questions = data.pop('questions', [])

            evaluation, created = Evaluation.objects.get_or_create(
                **data,
                technology=tech,
                publisher=admin_user,
                defaults={
                    'image': tech.image,
                }
            )

            if not created:
                if force:
                    # Mise à jour de l'évaluation existante
                    for key, value in data.items():
                        setattr(evaluation, key, value)
                    evaluation.image = tech.image
                    evaluation.save()
                    
                    # Suppression des anciennes questions pour recréer toutes les nouvelles
                    Question.objects.filter(evaluation=evaluation).delete()
                    
                    self.stdout.write(self.style.WARNING(
                        f'Évaluation "{evaluation.title}" mise à jour avec succès.'))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'Évaluation "{evaluation.title}" already exists. Skipping file {data_file.name}.'))
                    return

            questions_obj = []
            choices_data = []
            for q_data in questions:
                choices = q_data.pop('choices', [])
                question = Question(
                    **q_data,
                    evaluation=evaluation,
                    publisher=admin_user,
                    status=Question.Status.PUBLISHED,
                    technology=evaluation.technology,
                )
                questions_obj.append(question)
                choices_data.append(choices)

            questions_obj = Question.objects.bulk_create(questions_obj)
            choices_obj = []
            for i, question in enumerate(questions_obj):
                choices = choices_data[i]
                shuffle(choices)
                for c_data in choices:
                    choice = Choice(
                        question=question,
                        **c_data,
                    )
                    choices_obj.append(choice)
            Choice.objects.bulk_create(choices_obj)

            action = "mise à jour" if not created else "créée"
            self.stdout.write(self.style.SUCCESS(
                f'Évaluation "{evaluation.title}" {action} avec succès avec {len(questions)} questions.'))
