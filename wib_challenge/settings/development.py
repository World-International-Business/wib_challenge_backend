from .base import *

DEBUG = True

INTERNAL_IPS = [
    '127.0.0.1',
]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

INSTALLED_APPS.append('debug_toolbar')

MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ALLOWED_HOSTS.append('*')
