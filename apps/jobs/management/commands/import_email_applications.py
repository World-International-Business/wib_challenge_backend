from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import RecruitmentEmailInbox
from services.recruitment_email import analyze_pending_messages, sync_inbox


class Command(BaseCommand):
    help = 'Synchronise les dossiers IMAP configurés par organisation, sans modifier les emails.'

    def add_arguments(self, parser):
        parser.add_argument('--organization', type=int)
        parser.add_argument('--inbox', type=int)
        parser.add_argument('--analyze', action='store_true', help='Analyse aussi la file persistante, sans broker Celery.')

    def handle(self, *args, **options):
        inboxes = RecruitmentEmailInbox.objects.filter(enabled=True, verified_at__isnull=False)
        if options['organization']:
            inboxes = inboxes.filter(organization_id=options['organization'])
        if options['inbox']:
            inboxes = inboxes.filter(pk=options['inbox'])
        if not inboxes.exists():
            raise CommandError('Aucune connexion email activée et vérifiée pour cette sélection.')
        failed = False
        for inbox in inboxes.order_by('pk'):
            result = sync_inbox(inbox.pk)
            self.stdout.write(f'Inbox {inbox.pk}: {result}')
            failed = failed or result['status'] == 'failed'
            if options['analyze']:
                self.stdout.write(f'Inbox {inbox.pk}: {analyze_pending_messages(inbox.pk)}')
        if failed:
            raise CommandError('Certaines synchronisations ont échoué ; consultez les codes ci-dessus.')
