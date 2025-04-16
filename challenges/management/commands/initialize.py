from django.core.management import BaseCommand, call_command

from challenges.models import Settings


class Command(BaseCommand):
    help = 'Popularisation de la base de données'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Creating Default Settings'))
        call_command('create_default_settings')
        settings = Settings.objects.first()
        if settings.is_database_already_populated:
            self.stdout.write(self.style.WARNING('Database Already Popularized'))
            return
        self.stdout.write(self.style.NOTICE('Creating Default Admin'))
        call_command('create_default_admin')
        self.stdout.write(self.style.NOTICE('Creating Default Questions'))
        call_command('create_default_questions')
        self.stdout.write(self.style.NOTICE('Database is popularized'))
        settings.is_database_already_populated = True
        settings.save()
