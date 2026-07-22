import os

from .base import *

DEBUG = True

INTERNAL_IPS = [
    '127.0.0.1',
]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

USE_DEBUG_TOOLBAR = os.getenv('USE_DEBUG_TOOLBAR', 'False').lower() in ('1', 'true', 'yes')

if USE_DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ALLOWED_HOSTS.append('*')
