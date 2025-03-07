import json
from pathlib import Path

from django.core.management import BaseCommand
from django.db import transaction
from django.utils.text import slugify


class Command(BaseCommand):
    help = 'Import questions from a JSON file'

    data_dir = Path(__file__).resolve().parent / 'data'

    def add_arguments(self, parser):
        parser.add_argument('file.json', type=str)

    def check_data(self, data):
        if not isinstance(data, dict):
            self.stderr.write('Invalid data')
            return False
        if 'domain' not in data or not data['domain']:
            self.stderr.write('Missing domain')
            return False
        if 'category' not in data or not data['category']:
            self.stderr.write('Missing category')
            return False
        if 'criteria' not in data or not data['criteria']:
            self.stderr.write('Missing criteria')
            return False
        if 'questions' not in data or not data['questions']:
            self.stderr.write('Missing questions')
            return False
        return True

    def merge_question(self, q1, q2):
        for key in q2:
            if isinstance(q1[key], list) and isinstance(q2[key], list):
                if key == 'choices':
                    q1[key] = q2[key]
                else:
                    q1[key] = list(set((*q1[key], *q2[key])))
            else:
                q1[key] = q2[key]
        return q1

    def merge_file_data(self, file: Path, data: dict):
        def same_question(q1, q2):
            return (
                    q1['title'].strip() == q2['title'].strip() and
                    q1['question_type'].strip() == q2['question_type'].strip() and
                    q1['level'] == q2['level']
            )

        old_data = json.loads(file.read_text(encoding='utf-8'))
        old_data['domain'] = data['domain']
        old_data['category'] = data['category']
        old_data['criteria'] = data['criteria']
        old_data['tags'] = list(set([*old_data['tags'], *data['tags']]))
        for question in data['questions']:
            old_question_index = next(
                (i for i, q in enumerate(old_data['questions']) if same_question(q, question)),
                None
            )
            if old_question_index is not None:
                old_data['questions'][old_question_index] = self.merge_question(
                    old_data['questions'][old_question_index], question
                )
                self.stdout.write(self.style.SUCCESS(f'Merging Question {question['title']}'))
            else:
                old_data['questions'].append(question)
        return old_data

    @transaction.atomic
    def handle(self, *args, **options):
        self.data_dir.mkdir(exist_ok=True)
        file = options['file.json']
        file_path = Path(file)
        if not file_path.exists():
            self.stderr.write(f'File {file} does not exist')
            return
        if file_path.is_dir():
            self.stderr.write(f'{file} is a directory')
            return
        if file_path.suffix != '.json':
            self.stderr.write(f'{file} is not a JSON file')
            return
        self.stdout.write(f'Importing questions from {file}')

        data = json.loads(file_path.read_text(encoding='utf-8'))

        if not self.check_data(data):
            return

        dest_file = self.data_dir / slugify(data['domain'].strip()) / slugify(data['category'].strip()) / slugify(
            data['criteria'].strip()
        )
        dest_file = dest_file.with_suffix('.json')

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        if dest_file.exists():
            merged = self.merge_file_data(dest_file, data)
            dest_file.write_text(json.dumps(merged, indent=4, ensure_ascii=False), encoding='utf-8')
            self.stdout.write(f'Questions merged with {dest_file}')
        else:
            dest_file.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding='utf-8')
            self.stdout.write(f'Questions imported to {dest_file}')
