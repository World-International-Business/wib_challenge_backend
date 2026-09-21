import os

from .base import *

DEBUG = True

INTERNAL_IPS = [
    '127.0.0.1',
]

# Ajouter Whitenoise pour servir les fichiers statiques
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Configuration Whitenoise pour servir depuis staticfiles directement
WHITENOISE_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = True

# Configuration email avec fallback intelligent
EMAIL_BACKEND = 'wib_challenge.settings.email_config.SafeEmailBackend'
EMAIL_HOST = os.getenv('SMTP_HOST', os.getenv('EMAIL_HOST', 'smtp.gmail.com'))
EMAIL_PORT = int(os.getenv('SMTP_PORT', os.getenv('EMAIL_PORT', '587')))
EMAIL_HOST_USER = os.getenv('SMTP_USER', os.getenv('EMAIL_HOST_USER', ''))
EMAIL_HOST_PASSWORD = os.getenv(
    'SMTP_PASSWORD',
    os.getenv('EMAIL_HOST_PASSWORD', ''),
).replace(' ', '')
EMAIL_USE_TLS = os.getenv(
    'SMTP_USE_TLS',
    os.getenv('EMAIL_USE_TLS', 'True'),
).lower() in ('1', 'true', 'yes')
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() in ('1', 'true', 'yes')
DEFAULT_FROM_EMAIL = os.getenv(
    'SMTP_FROM',
    os.getenv('DEFAULT_FROM_EMAIL', 'noreply@wib-challenge.com'),
)
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

# Options additionnelles pour la fiabilite
EMAIL_TIMEOUT = 30
EMAIL_SUBJECT_PREFIX = '[WIB Challenge] '

# Configuration des fichiers statiques en développement
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'collected_static'
STATICFILES_DIRS = [
    BASE_DIR / 'staticfiles',
]

USE_DEBUG_TOOLBAR = os.getenv('USE_DEBUG_TOOLBAR', 'False').lower() in ('1', 'true', 'yes')

if USE_DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ALLOWED_HOSTS.append('*')
