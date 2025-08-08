import json
import mimetypes
import urllib.request
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from django.db import transaction

from apps.core.models import Profession, Technology, Domain

default_data_dir = Path(__file__).parent / 'data'


class Command(BaseCommand):
    help = 'Seed core data'

    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Force seed even if data already exists')
        parser.add_argument('--data-dir', type=str, default=default_data_dir,
                            help='Directory containing seed data files')

    @staticmethod
    def download_image(url: str):
        response = urllib.request.urlopen(url)
        ext = mimetypes.guess_extension(response.info().get_content_type())
        if ext is None:
            ext = '.png'
        file = uuid4().hex + ext
        return file, response.read()

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = Path(options['data_dir']).resolve()
        force = options.get('force', False)

        if not data_dir.exists():
            self.stdout.write(self.style.ERROR(
                f'Data directory {data_dir} does not exist'))
            return

        # L'option force est maintenant utilisée pour mettre à jour les données existantes
        # au lieu de les supprimer

        with open(data_dir / 'domains.json', 'r', encoding='utf-8') as f:
            domains = json.load(f)
            for domain_data in domains:
                domain, created = Domain.objects.update_or_create(
                    name=domain_data['name'],
                    defaults={'description': domain_data.get('description', '')}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f"Created domain: {domain.name}"))
                elif force:
                    self.stdout.write(self.style.SUCCESS(
                        f"Updated domain: {domain.name}"))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Domain {domain.name} already exists"))
        self.stdout.write(self.style.SUCCESS('Successfully seeded domains'))

        with open(data_dir / 'technologies.json', 'r', encoding='utf-8') as f:
            technologies = json.load(f)
            for tech in technologies:
                technology, created = Technology.objects.get_or_create(
                    name=tech['name'])
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f'Created {tech["name"]}'))
                    file, content = self.download_image(tech['url'])
                    technology.image.save(file, ContentFile(content))
                elif force:
                    self.stdout.write(self.style.SUCCESS(
                        f'Updating {tech["name"]}'))
                    file, content = self.download_image(tech['url'])
                    technology.image.delete(save=False)
                    technology.image.save(file, ContentFile(content))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'{tech["name"]} already exists'))
        self.stdout.write(self.style.SUCCESS(
            'Successfully seeded technologies'))

        with open(data_dir / 'professions.json', 'r', encoding='utf-8') as f:
            professions = json.load(f)

            default_domain = Domain.objects.first()
            if not default_domain:
                self.stdout.write(self.style.ERROR(
                    'No domain found, please seed domains first'))
                return

            for profession in professions:
                if isinstance(profession, str):
                    prof_obj, created = Profession.objects.update_or_create(
                        title=profession,
                        defaults={'domain': default_domain}
                    )

                else:
                    domain_name = profession.get('domain', None)
                    domain = None
                    if domain_name:
                        try:
                            domain = Domain.objects.get(name=domain_name)
                        except Domain.DoesNotExist:
                            self.stdout.write(self.style.WARNING(
                                f'Domain {domain_name} not found, using default'))
                            domain = default_domain
                    else:
                        domain = default_domain

                    prof_obj, created = Profession.objects.update_or_create(
                        title=profession['title'],
                        defaults={'domain': domain}
                    )

                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f'Created {prof_obj.title}'))
                elif force:
                    self.stdout.write(self.style.SUCCESS(
                        f'Updated {prof_obj.title}'))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'{prof_obj.title} already exists'))
        self.stdout.write(self.style.SUCCESS(
            'Successfully seeded professions'))

        with open(data_dir / 'profession_technologies.json', 'r', encoding='utf-8') as f:
            profession_technologies = json.load(f)

            for item in profession_technologies:
                profession_title = item['profession']
                tech_names = item['technologies']

                try:
                    profession = Profession.objects.get(title=profession_title)
                    current_techs = set(
                        profession.technologies.values_list('name', flat=True))
                    new_techs = []

                    for tech_name in tech_names:
                        if tech_name not in current_techs:
                            try:
                                tech = Technology.objects.get(name=tech_name)
                                new_techs.append(tech)
                            except Technology.DoesNotExist:
                                self.stdout.write(self.style.WARNING(
                                    f'Technology {tech_name} does not exist'))

                    if new_techs:
                        profession.technologies.add(*new_techs)
                        self.stdout.write(self.style.SUCCESS(
                            f'Added {len(new_techs)} technologies to {profession_title}'
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'No new technologies for {profession_title}'))

                except Profession.DoesNotExist:
                    self.stdout.write(self.style.ERROR(
                        f'Profession {profession_title} does not exist'))

        self.stdout.write(self.style.SUCCESS(
            'Successfully linked technologies to professions'))
