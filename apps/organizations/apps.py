from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.organizations'

    def ready(self):
        # Import signals to register receivers
        try:
            import apps.organizations.signals  # noqa: F401
        except Exception:
            # Avoid crashing app startup if signals have import-time dependencies not ready yet
            pass
