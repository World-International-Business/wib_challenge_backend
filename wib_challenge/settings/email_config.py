"""
Configuration email amelioree avec gestion des erreurs et fallback
"""
import os
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.backends.console import ConsoleEmailBackend
import logging

logger = logging.getLogger(__name__)


class SafeEmailBackend:
    """
    Backend email intelligent qui fallback vers console si SMTP echoue
    """
    def __init__(self, *args, **kwargs):
        self.use_smtp = os.getenv('EMAIL_PROVIDER', '').lower() == 'smtp'
        self.smtp_configured = bool(
            os.getenv('SMTP_USER') or os.getenv('EMAIL_HOST_USER')
        )
        
        if self.use_smtp and self.smtp_configured:
            try:
                self.backend = EmailBackend(*args, **kwargs)
                logger.info("Backend SMTP configure")
            except Exception as e:
                logger.warning(f"Erreur configuration SMTP: {e}, fallback vers console")
                self.backend = ConsoleEmailBackend(*args, **kwargs)
        else:
            logger.info("Backend console (pas de configuration SMTP)")
            self.backend = ConsoleEmailBackend(*args, **kwargs)
    
    def __getattr__(self, name):
        return getattr(self.backend, name)


def get_email_backend():
    """Retourne le backend email approprie"""
    return 'wib_challenge.settings.email_config.SafeEmailBackend'