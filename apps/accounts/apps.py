from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = _('Comptes Utilisateurs')

    def ready(self):
        post_migrate.connect(self.call_management_command, sender=self)

    def call_management_command(self, *args, **kwargs):
        call_command('create_default_admin')
