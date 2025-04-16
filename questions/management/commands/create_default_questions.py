import json
from pathlib import Path

from django.core.management import BaseCommand
from django.db import transaction, models

from questions.models import Tag, Question, Domain, Category, Criteria, Choice


class Command(BaseCommand):
    help = 'Create default questions'

    data_dir = Path(__file__).resolve().parent / 'data'

    def get_or_create_model(self, model: models.Model, defaults=None, **kwargs):
        obj, created = model.objects.get_or_create( **kwargs)
        if created:
            self.stdout.write(self.style.SUCCESS(f'Creating Model {model._meta.verbose_name} {obj}'))
        return obj, created

    @transaction.atomic
    def handle(self, *args, **options):
        self.data_dir.mkdir(exist_ok=True)

        files = self.data_dir.glob('**/*.json')
        for file in files:
            data = json.loads(file.read_text(encoding='utf-8'))
            self.stdout.write(f'Importing questions from {file.name}\n')

            domain, _ = self.get_or_create_model(Domain, name=data['domain'].strip())
            category, _ = self.get_or_create_model(Category, name=data['category'].strip(), domain=domain)
            criteria, _ = self.get_or_create_model(Criteria, name=data['criteria'].strip(), category=category)

            tags_dict = {}
            for tag in data.get('tags', []):
                obj, _ = self.get_or_create_model(Tag, name=tag, criteria=criteria)
                tags_dict[tag] = obj

            for question_data in data.get('questions', []):
                question, created = self.get_or_create_model(
                    Question,
                    title=question_data['title'],
                    description=question_data['description'] if 'description' in question_data else None,
                    level=question_data['level'],
                    question_type=question_data['question_type'],
                    category=category
                )

                if not created:
                    continue

                question.tags.set([tags_dict[tag] for tag in question_data['tags'] if tag in tags_dict])

                if question.is_multiple_choice or question.is_unique_choice:
                    for choice_data in question_data['choices']:
                        self.get_or_create_model(
                            Choice,
                            question=question,
                            text=choice_data['text'],
                            is_correct=choice_data['is_correct']
                        )
