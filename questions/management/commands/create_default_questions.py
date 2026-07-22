import json
from pathlib import Path
from typing import Type

from django.core.management import BaseCommand
from django.db import transaction, models

from questions.models import Tag, Question, Domain, Category, Criteria, Choice


class Command(BaseCommand):
    help = 'Create default questions'

    data_dir = Path(__file__).resolve().parent / 'data'

    def get_or_create_model(self, model: Type[models.Model], defaults=None, **kwargs):
        obj, created = model.objects.get_or_create(**kwargs, defaults=defaults)
        if created:
            self.stdout.write(self.style.SUCCESS(f'Creating Model {model._meta.verbose_name} {obj}'))
        return obj, created

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', type=str, help='Directory containing JSON files with questions data',
                            default=self.data_dir)
        parser.add_argument('--force', action='store_true',
                            help='Force creation of questions even if they already exist')

    @transaction.atomic
    def handle(self, *args, **options):
        self.data_dir = Path(options['data_dir']).resolve().absolute()
        self.force = options['force']
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
                obj, _ = self.get_or_create_model(Tag, name=tag, criteria__category__domain=domain,
                                                  defaults={'criteria': criteria})
                tags_dict[tag] = obj

            # Récupérer la catégorie de question par défaut du fichier JSON s'il existe
            default_question_category = data.get('question_category', 'NORMAL')

            for question_data in data.get('questions', []):
                # Log du traitement de la question
                self.stdout.write(f'Processing question: {question_data["title"]}')
                
                question, created = self.get_or_create_model(
                    Question,
                    title=question_data['title'],
                    level=int(question_data['level']),
                    question_type=question_data['question_type'],
                    defaults={
                        'category': category,
                        'description': question_data.get('description', None),
                        'question_category': question_data.get('question_category', default_question_category),
                    }
                )

                if not created:
                    if self.force:
                        # Mettre à jour la question existante
                        self.stdout.write(f'Force update enabled - updating question: {question.title}')
                        question.category = category
                        question.description = question_data.get('description', None)
                        question.question_category = question_data.get('question_category', default_question_category)
                        question.save()
                        self.stdout.write(self.style.SUCCESS(f'Updating Question: {question.title}'))
                    else:
                        self.stdout.write(f'Skipping existing question: {question.title} (use --force to update)')
                        continue

                # Log des tags associés
                tags_to_add = [tags_dict[tag] for tag in question_data['tags'] if tag in tags_dict]
                self.stdout.write(f'Setting {len(tags_to_add)} tags for question: {question.title}')
                question.tags.set(tags_to_add)

                if question.is_multiple_choice or question.is_unique_choice:
                    # Log du type de question
                    question_type = "multiple choice" if question.is_multiple_choice else "unique choice"
                    self.stdout.write(f'Processing {question_type} question: {question.title}')
                    
                    # Si on force la mise à jour, on supprime d'abord les choix existants
                    if not created and self.force:
                        deleted_count = Choice.objects.filter(question=question).count()
                        Choice.objects.filter(question=question).delete()
                        self.stdout.write(f'Deleted {deleted_count} existing choices for question: {question.title}')
                    
                    choices = []
                    for i, choice_data in enumerate(question_data['choices']):
                        choice = Choice(question=question, text=choice_data['text'],
                                        is_correct=choice_data['is_correct'])
                        choices.append(choice)
                        is_correct_str = "correct" if choice_data['is_correct'] else "incorrect"
                        self.stdout.write(f'  Choice {i+1}: {choice_data["text"]} ({is_correct_str})')
                    Choice.objects.bulk_create(choices)
