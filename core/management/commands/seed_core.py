from django.core.management import BaseCommand
from pathlib import Path
import json
import urllib
from core.models import Profession, Technology  
from django.conf import settings
from django.db import transaction

class Command(BaseCommand):
    help = 'Seed core data'

    requires_migrations_checks = True
    
    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force seed even if data already exists')
    
        
    def download_image(self, url: str, destination: Path):
        response = urllib.request.urlopen(url)
        destination.mkdir(parents=True, exist_ok=True)
        file = (destination / url.split('/')[-1] ).with_suffix('.png')
        with open(file, 'wb') as f:
            f.write(response.read())
        return file.name

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir  = Path(__file__).parent / 'data'
        media = Path(settings.MEDIA_ROOT)
        
        with open(data_dir / 'profession.json', 'r', encoding='utf-8') as f:
            professions = json.load(f)
            for profession in professions:
                _, created = Profession.objects.get_or_create(title=profession)
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created {profession}'))
                else:
                    self.stdout.write(self.style.WARNING(f'{profession} already exists'))
        self.stdout.write(self.style.SUCCESS('Successfully seeded professions'))
    
        with open(data_dir / 'technologies.json', 'r', encoding='utf-8') as f:
            technologies = json.load(f)
            for tech in technologies:
                technology, created = Technology.objects.get_or_create(name=tech['name'])
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created {tech}'))
                    technology.image = self.download_image(tech['url'], media / 'technologies')
                    technology.save()
                else:
                    self.stdout.write(self.style.WARNING(f'{tech} already exists'))
        self.stdout.write(self.style.SUCCESS('Successfully seeded technologies'))