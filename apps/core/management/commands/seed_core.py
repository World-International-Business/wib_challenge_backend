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

    @staticmethod
    def _generate_tech_svg(technology, name):
        """Génère un SVG de fallback avec les initiales de la technologie."""
        import hashlib
        # Couleur basée sur le hash du nom
        hash_int = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
        hue = hash_int % 360
        color1 = f'hsl({hue}, 60%, 45%)'
        color2 = f'hsl({(hue + 30) % 360}, 70%, 35%)'
        # Initiales (max 2 caractères)
        initials = ''.join([w[0] for w in name.split()[:2]]).upper() if name else '?'
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{color1}" />
      <stop offset="100%" style="stop-color:{color2}" />
    </linearGradient>
  </defs>
  <rect width="200" height="200" rx="20" fill="url(#g)"/>
  <text x="100" y="115" font-family="Arial, sans-serif" font-size="60" font-weight="bold"
        fill="white" text-anchor="middle">{initials}</text>
</svg>'''
        filename = f'{name.lower().replace(" ", "-").replace("/", "-")[:40]}.svg'
        technology.image.save(filename, ContentFile(svg.encode('utf-8')), save=False)
        technology.save()

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
                    if tech.get('url'):
                        try:
                            file, content = self.download_image(tech['url'])
                            technology.image.save(file, ContentFile(content))
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(
                                f'Failed to download image for {tech["name"]}: {e}'))
                            # Fallback : générer un SVG avec les initiales
                            self._generate_tech_svg(technology, tech['name'])
                    else:
                        # Pas d'URL -> SVG de fallback
                        self._generate_tech_svg(technology, tech['name'])
                elif force:
                    # Vérifier si l'image existe en base mais le fichier est manquant
                    if technology.image and not technology.image.storage.exists(technology.image.name):
                        self.stdout.write(self.style.WARNING(
                            f'{tech["name"]} image file missing, regenerating...'))
                        technology.image = None
                    if not technology.image and tech.get('url'):
                        try:
                            file, content = self.download_image(tech['url'])
                            technology.image.save(file, ContentFile(content))
                            self.stdout.write(self.style.SUCCESS(
                                f'Updated {tech["name"]}'))
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(
                                f'Failed to download image for {tech["name"]}: {e}'))
                            # Fallback : générer un SVG avec les initiales
                            self._generate_tech_svg(technology, tech['name'])
                    elif not technology.image:
                        # Pas d'URL mais pas d'image non plus -> SVG de fallback
                        self._generate_tech_svg(technology, tech['name'])
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'{tech["name"]} already exists'))
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
