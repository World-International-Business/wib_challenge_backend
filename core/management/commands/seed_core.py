import json
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from django.db import transaction

from core.models import Profession, Technology


class Command(BaseCommand):
    help = 'Seed core data'

    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force seed even if data already exists')

    @staticmethod
    def download_image(url: str, destination: Path):
        response = urllib.request.urlopen(url)
        destination.mkdir(parents=True, exist_ok=True)
        file = url.split('/')[-1] + '.png'
        return file, response.read()

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = Path(__file__).parent / 'data'
        media = Path(settings.MEDIA_ROOT)

        # Chargement des technologies
        with open(data_dir / 'technologies.json', 'r', encoding='utf-8') as f:
            technologies = json.load(f)
            for tech in technologies:
                technology, created = Technology.objects.get_or_create(name=tech['name'])
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created {tech["name"]}'))
                    file, content = self.download_image(tech['url'], media / 'technologies')
                    if technology.image and technology.image.path:
                        pass
                    technology.image.save(file, ContentFile(content))
                else:
                    self.stdout.write(self.style.WARNING(f'{tech["name"]} already exists'))
        self.stdout.write(self.style.SUCCESS('Successfully seeded technologies'))

        # Chargement des professions
        with open(data_dir / 'professions.json', 'r', encoding='utf-8') as f:
            professions = json.load(f)
            for profession in professions:
                _, created = Profession.objects.get_or_create(title=profession)
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created {profession}'))
                else:
                    self.stdout.write(self.style.WARNING(f'{profession} already exists'))
        self.stdout.write(self.style.SUCCESS('Successfully seeded professions'))

        # Association des technologies aux professions
        with open(data_dir / 'profession_technologies.json', 'r', encoding='utf-8') as f:
            profession_technologies = json.load(f)

            for item in profession_technologies:
                profession_title = item['profession']
                tech_names = item['technologies']

                try:
                    profession = Profession.objects.get(title=profession_title)
                    current_techs = set(profession.technologies.values_list('name', flat=True))
                    new_techs = []

                    for tech_name in tech_names:
                        if tech_name not in current_techs:
                            try:
                                tech = Technology.objects.get(name=tech_name)
                                new_techs.append(tech)
                            except Technology.DoesNotExist:
                                self.stdout.write(self.style.WARNING(f'Technology {tech_name} does not exist'))

                    if new_techs:
                        profession.technologies.add(*new_techs)
                        self.stdout.write(self.style.SUCCESS(
                            f'Added {len(new_techs)} technologies to {profession_title}'
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(f'No new technologies for {profession_title}'))

                except Profession.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Profession {profession_title} does not exist'))

        self.stdout.write(self.style.SUCCESS('Successfully linked technologies to professions'))
