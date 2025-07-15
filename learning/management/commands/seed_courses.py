import json
from pathlib import Path

from django.core.management import BaseCommand
from django.db import transaction

from learning.models import Course, Module, Content, Quiz, QuizQuestion, QuizChoice


class Command(BaseCommand):
    help = 'Seed Courses data'

    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Force seed even if data already exists')

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = Path(__file__).resolve().parent / 'data'
        force = options.get('force', False)

        if not data_dir.exists():
            self.stdout.write(
                self.style.ERROR(f'Data directory not found: {data_dir}')
            )
            return

        json_files = list(data_dir.glob('*.json'))
        if not json_files:
            self.stdout.write(
                self.style.WARNING('No JSON files found in data directory')
            )
            return

        self.stdout.write(f'Found {len(json_files)} JSON files to process')

        for file in json_files:
            try:
                self.import_from_json(file, force)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing {file.name}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS('Course seeding completed successfully')
        )

    def import_from_json(self, data_file: Path, force=False):
        """Import course data from JSON file"""
        with data_file.open(encoding='utf-8') as f:
            data = json.load(f)

        course_title = data.get('title')
        if not course_title:
            self.stdout.write(
                self.style.ERROR(f'Missing title in {data_file.name}')
            )
            return

        existing_course = Course.objects.filter(title=course_title).first()

        if existing_course and not force:
            self.stdout.write(
                self.style.WARNING(f'Course "{course_title}" already exists. Use --force to update.')
            )
            return

        course = self.create_or_update_course(data, existing_course, force)

        if course:
            self.stdout.write(
                self.style.SUCCESS(f'{"Updated" if existing_course else "Created"} course: {course_title}')
            )

            modules_data = data.get('modules', [])
            self.process_modules(course, modules_data, force)

    def create_or_update_course(self, data, existing_course=None, force=False):
        """Create or update a course"""
        course_data = {
            'title': data.get('title'),
            'description': data.get('description', ''),
            'level': data.get('level', 'beginner'),
            'is_free': data.get('is_free', True)
        }

        if existing_course and force:
            existing_course.modules.all().delete()
            for field, value in course_data.items():
                setattr(existing_course, field, value)
            existing_course.save()
            return existing_course
        elif not existing_course:
            return Course.objects.create(**course_data)

        return existing_course

    def process_modules(self, course, modules_data, force=False):
        """Process modules for a course"""

        for module_data in modules_data:
            module_title = module_data.get('title')
            if not module_title:
                continue

            module = Module.objects.create(
                course=course,
                title=module_title,
                description=module_data.get('description', '')
            )

            self.stdout.write(f'\tCreated module: {module_title}')

            contents_data = module_data.get('contents', [])
            self.process_contents(module, contents_data)

            quiz_data = module_data.get('quiz')
            if quiz_data:
                self.process_quiz(module, quiz_data)

    def process_contents(self, module, contents_data):
        """Process contents for a module"""
        for content_data in contents_data:
            content_title = content_data.get('title')
            if not content_title:
                continue

            content = Content.objects.create(
                module=module,
                title=content_title,
                content_type=content_data.get('content_type', 'markdown'),
                resource_file=content_data.get('resource_file'),
                resource_url=content_data.get('resource_url'),
                content=content_data.get('content', '')
            )

            self.stdout.write(f'\t\tCreated content: {content_title}')

    def process_quiz(self, module, quiz_data):
        """Process quiz for a module"""
        quiz_title = quiz_data.get('title')
        if not quiz_title:
            return

        quiz = Quiz.objects.create(
            module=module,
            title=quiz_title,
            description=quiz_data.get('description', '')
        )

        self.stdout.write(f'\t\tCreated quiz: {quiz_title}')

        questions_data = quiz_data.get('questions', [])
        self.process_quiz_questions(quiz, questions_data)

    def process_quiz_questions(self, quiz, questions_data):
        """Process questions for a quiz"""
        for question_data in questions_data:
            question_title = question_data.get('title')
            if not question_title:
                continue

            question = QuizQuestion.objects.create(
                quiz=quiz,
                title=question_title,
                description=question_data.get('description', ''),
                explanation=question_data.get('explanation', '')
            )

            self.stdout.write(f'\t\t\tCreated question: {question_title}')

            choices_data = question_data.get('choices', [])
            self.process_quiz_choices(question, choices_data)

    def process_quiz_choices(self, question, choices_data):
        """Process choices for a quiz question"""
        for choice_data in choices_data:
            choice_text = choice_data.get('text')
            if not choice_text:
                continue

            QuizChoice.objects.create(
                question=question,
                text=choice_text,
                is_correct=choice_data.get('is_correct', False)
            )

            self.stdout.write(f'\t\t\t\tCreated choice: {choice_text}')
