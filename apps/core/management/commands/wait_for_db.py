import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Django command to wait for database to be available"""

    help = "Attend que la base de donne soit disponible"

    def handle(self, *args, **options):
        self.stdout.write('Waiting for database...')
        db_conn = None
        while not db_conn:
            try:
                connection = connection['default']
                connection.ensure_connection()
                db_conn = True
            except OperationalError:
                #log important ;voir l erreur exacte
                self.stdout.write(str(self.style.ERROR(f'Databaseerror:{e}')))
                self.stdout.write('Database unavailable, waiting 1 second...')
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS('Database available!'))
