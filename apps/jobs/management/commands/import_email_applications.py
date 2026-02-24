from django.core.management.base import BaseCommand

from services.email_applications import import_email_applications_from_imap


class Command(BaseCommand):
    help = "Importe les candidatures depuis la boîte email RH globale (IMAP)"

    def handle(self, *args, **options):
        result = import_email_applications_from_imap()

        self.stdout.write(self.style.NOTICE(
            f"Emails UNSEEN traités: {result['processed']} | "
            f"candidatures créées: {result['created']} | "
            f"emails ignorés: {result['skipped']}"
        ))

        if result.get('errors'):
            for err in result['errors']:
                self.stderr.write(self.style.WARNING(err))

        self.stdout.write(self.style.SUCCESS("Import des candidatures email terminé."))
