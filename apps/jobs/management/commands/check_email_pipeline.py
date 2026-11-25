from pathlib import Path
from tempfile import TemporaryFile

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from services.channel_crypto import decrypt_secret, encrypt_secret
from services.email_storage import RecruitmentResumeStorage


class Command(BaseCommand):
    help = 'Vérifie les prérequis du pipeline email sans lire de messagerie ni envoyer de mail.'

    def add_arguments(self, parser):
        parser.add_argument('--require-shared-database', action='store_true')
        parser.add_argument('--broker', action='store_true')

    def handle(self, *args, **options):
        if options['require_shared_database'] and connection.vendor not in ('postgresql', 'mysql'):
            raise CommandError('Les conteneurs web et worker doivent utiliser la même base PostgreSQL/MySQL, pas des fichiers SQLite séparés.')
        try:
            connection.ensure_connection()
            private_root = Path(RecruitmentResumeStorage().location)
            private_root.mkdir(parents=True, exist_ok=True)
            with TemporaryFile(dir=private_root) as probe:
                probe.write(b'pipeline-healthcheck')
                probe.flush()
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                raise CommandError('Appliquez les migrations avant de démarrer le pipeline email.')
            if decrypt_secret(encrypt_secret('pipeline-healthcheck')) != 'pipeline-healthcheck':
                raise CommandError('Chiffrement indisponible.')
        except CommandError:
            raise
        except Exception:
            raise CommandError('Base de données, stockage privé ou chiffrement indisponible. Vérifiez la configuration sans publier les secrets.')
        if options['broker']:
            try:
                from wib_challenge.celery import app
                with app.connection_for_write() as broker:
                    broker.ensure_connection(max_retries=0, timeout=5)
            except Exception:
                raise CommandError('Broker Celery indisponible.')
        self.stdout.write(self.style.SUCCESS('Prérequis email vérifiés. Démarrez un worker Celery et une seule instance de Beat.'))
