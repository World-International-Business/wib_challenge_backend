import json
from pathlib import Path

from django.core.management import BaseCommand, call_command
from django.db import transaction

from apps.accounts.models import User
from apps.core.models import Technology
from apps.evaluations.models import Evaluation
from apps.questions.models import Question, Choice


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
        processed_files = 0

        for file in data_dir.glob('*.json'):
            try:
                self.import_from_json(file, admin_user, force)
                processed_files += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Error processing {file.name}: {str(e)}'))
                if hasattr(e, '__traceback__'):
                    import traceback
                    self.stdout.write(self.style.ERROR(
                        traceback.format_exc()))

        self.stdout.write(self.style.SUCCESS(
            f'Successfully processed {processed_files} evaluation files.'))

    def import_from_json(self, data_file: Path, admin_user: User, force=False):
        with data_file.open(encoding='utf-8') as f:
            data = json.load(f)
            tech_name = data.pop('technology')

            try:
                tech = Technology.objects.get(name__iexact=tech_name)
            except Technology.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'Technology "{tech_name}" not found. Skipping file {data_file.name}.'))
                return

            questions_data = data.pop('questions', [])

            evaluation, created = Evaluation.objects.update_or_create(
                title=data.get('title'),
                technology=tech,
                publisher=admin_user,
                defaults={
                    **data,
                    'image': tech.image,
                }
            )

            if not force and not created:
                self.stdout.write(self.style.WARNING(
                    f'Évaluation "{evaluation.title}" already exists. Use --force to update. Skipping file {data_file.name}.'))
                return

            existing_questions = {
                q.title.lower(): q for q in
                Question.objects.filter(technology=tech, publisher=admin_user)
            }

            nb_questions = 0

            for q_data in questions_data:
                choices = q_data.pop('choices', [])
                title = q_data.get('title')

                question = existing_questions.get(title.lower())

                if question:
                    for field, value in q_data.items():
                        if hasattr(question, field):
                            setattr(question, field, value)
                    question.status = Question.Status.PUBLISHED
                    question.save()

                    question.choices.all().delete()
                else:
                    question = Question.objects.create(
                        **q_data,
                        publisher=admin_user,
                        status=Question.Status.PUBLISHED,
                        technology=tech,
                    )

                nb_questions += 1
                Choice.objects.bulk_create([
                    Choice(question=question, **choice_data)
                    for choice_data in choices
                ])

                if not evaluation.questions.filter(pk=question.pk).exists():
                    evaluation.questions.add(question)

            self.stdout.write(self.style.SUCCESS(
                f'Successfully processed evaluation "{evaluation.title}" with {len(questions_data)} questions.'))

            action = "mise à jour" if not created else "créée"
            self.stdout.write(self.style.SUCCESS(
                f'Évaluation "{evaluation.title}" {action} avec succès avec {nb_questions} questions.'))
