import json
import hashlib
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from django.db import transaction

from apps.core.models import Technology
from apps.learning.models import Course, Module, Content, Quiz, QuizQuestion, QuizChoice


# Couleurs par technologie (nom en minuscule -> gradient)
TECH_GRADIENTS = {
    'python': ('#3776ab', '#ffd43b'),
    'cybersécurité': ('#1a1a2e', '#e94560'),
    'cybersecurite': ('#1a1a2e', '#e94560'),
    'data science': ('#764ba2', '#667eea'),
    'machine learning': ('#764ba2', '#667eea'),
    'intelligence artificielle': ('#764ba2', '#667eea'),
    'react': ('#61dafb', '#282c34'),
    'node.js': ('#68a063', '#3c873a'),
    'nodejs': ('#68a063', '#3c873a'),
    'docker': ('#2496ed', '#0db7ed'),
    'kubernetes': ('#326ce5', '#1e42a3'),
    'aws': ('#ff9900', '#232f3e'),
    'azure': ('#0078d4', '#00bcf2'),
    'scrum': ('#1a73e8', '#4285f4'),
    'agile': ('#1a73e8', '#4285f4'),
    'git': ('#f05032', '#e94e31'),
    'html': ('#e34c26', '#f06529'),
    'css': ('#264de4', '#2965f1'),
    'javascript': ('#f7df1e', '#323330'),
    'sql': ('#336791', '#4479a1'),
    'linux': ('#fcc624', '#000000'),
}

DEFAULT_GRADIENT = ('#0f4c81', '#1a5fa3')


def _gradient_for_course(course_title, skills):
    """Retourne un gradient (couleur1, couleur2) basé sur le titre ou les skills."""
    title_lower = course_title.lower()
    for skill in skills:
        skill_lower = skill.lower()
        for key, grad in TECH_GRADIENTS.items():
            if key in skill_lower or key in title_lower:
                return grad
    for key, grad in TECH_GRADIENTS.items():
        if key in title_lower:
            return grad
    return DEFAULT_GRADIENT


def _generate_course_svg(course_title, skills):
    """Génère un SVG de couverture pour un cours."""
    color1, color2 = _gradient_for_course(course_title, skills)
    # Hash pour un pattern unique par cours
    hash_hex = hashlib.md5(course_title.encode()).hexdigest()[:8]

    # Tronquer le titre pour l'affichage
    display_title = course_title if len(course_title) <= 30 else course_title[:27] + '...'

    # Technologies (skills) à afficher
    skills_text = ' • '.join(skills[:3]) if skills else 'Formation'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <defs>
    <linearGradient id="bg-{hash_hex}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{color1};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{color2};stop-opacity:1" />
    </linearGradient>
    <pattern id="dots-{hash_hex}" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
      <circle cx="20" cy="20" r="1.5" fill="white" opacity="0.1"/>
    </pattern>
  </defs>
  <rect width="600" height="400" fill="url(#bg-{hash_hex})"/>
  <rect width="600" height="400" fill="url(#dots-{hash_hex})"/>
  <rect x="0" y="280" width="600" height="120" fill="black" opacity="0.25"/>
  <text x="300" y="180" font-family="Arial, sans-serif" font-size="26" font-weight="bold"
        fill="white" text-anchor="middle" opacity="0.95">{display_title}</text>
  <text x="300" y="220" font-family="Arial, sans-serif" font-size="16"
        fill="white" text-anchor="middle" opacity="0.7">{skills_text}</text>
  <text x="300" y="340" font-family="Arial, sans-serif" font-size="14" font-weight="bold"
        fill="white" text-anchor="middle" opacity="0.6">WIB Challenge</text>
</svg>'''
    return svg


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
        skills = data.get('skills', [])
        if skills:
            course.skills.set(list(Technology.objects.filter(name__in=skills).values_list('id', flat=True)))

        if course:
            self.stdout.write(
                self.style.SUCCESS(f'{"Updated" if existing_course else "Created"} course: {course_title}')
            )

            modules_data = data.get('modules', [])
            self.process_modules(course, modules_data, force)

    def create_or_update_course(self, data, existing_course=None, force=False):
        """Create or update a course"""
        skills = data.get('skills', [])
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
            # Vérifier que le fichier image existe vraiment sur le disque
            # (en Docker, le volume media peut être éphémère à chaque redéploiement)
            if self._cover_missing(existing_course):
                self._assign_cover_svg(existing_course, data.get('title', ''), skills)
            existing_course.save()
            return existing_course
        elif not existing_course:
            course = Course.objects.create(**course_data)
            self._assign_cover_svg(course, data.get('title', ''), skills)
            course.save()
            return course

        return existing_course

    @staticmethod
    def _cover_missing(course):
        """Vrai si le cours n'a pas de couverture ou si le fichier n'existe plus sur le disque."""
        if not course.picture_cover:
            return True
        try:
            return not course.picture_cover.storage.exists(course.picture_cover.name)
        except Exception:
            return True

    def _assign_cover_svg(self, course, title, skills):
        """Génère et assigne une couverture SVG pour le cours."""
        try:
            from django.utils.text import slugify
            svg_content = _generate_course_svg(title, skills)
            filename = f'{slugify(title)[:50] or "course"}.svg'
            course.picture_cover.save(
                filename,
                ContentFile(svg_content.encode('utf-8')),
                save=False
            )
            self.stdout.write(f'\tGenerated cover image: {filename}')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Failed to generate cover for "{title}": {e}')
            )

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
