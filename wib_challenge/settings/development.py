import os

from .base import *

DEBUG = True

INTERNAL_IPS = [
    '127.0.0.1',
]

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend'
    if os.getenv('EMAIL_PROVIDER', '').lower() == 'smtp'
    else 'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.getenv('SMTP_HOST', os.getenv('EMAIL_HOST', 'smtp.gmail.com'))
EMAIL_PORT = int(os.getenv('SMTP_PORT', os.getenv('EMAIL_PORT', '587')))
EMAIL_HOST_USER = os.getenv('SMTP_USER', os.getenv('EMAIL_HOST_USER', ''))
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASSWORD', os.getenv('EMAIL_HOST_PASSWORD', ''))
EMAIL_USE_TLS = os.getenv(
    'SMTP_USE_TLS',
    os.getenv('EMAIL_USE_TLS', 'True'),
).lower() in ('1', 'true', 'yes')
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() in ('1', 'true', 'yes')
DEFAULT_FROM_EMAIL = os.getenv(
    'SMTP_FROM',
    os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER),
)
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

USE_DEBUG_TOOLBAR = os.getenv('USE_DEBUG_TOOLBAR', 'False').lower() in ('1', 'true', 'yes')

if USE_DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ALLOWED_HOSTS.append('*')
