import os

import dj_database_url

from .base import *

DEBUG = False

SECRET_KEY = os.getenv('SECRET_KEY')

DATABASES['default'] = dj_database_url.config(conn_max_age=600, conn_health_checks=True)

if not DATABASES['default']['ENGINE'].endswith('sqlite'):
    DATABASES['default']['OPTIONS'] = {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        'charset': 'utf8mb4',
    }

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS').split(',')

SECURE_HSTS_SECONDS = True

SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True

CSRF_COOKIE_SECURE = True

SECURE_HSTS_INCLUDE_SUBDOMAINS = True

SECURE_HSTS_PRELOAD = True

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'

EMAIL_PORT = 587

EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')

EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

EMAIL_USE_TLS = True

EMAIL_USE_SSL = False

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

SERVER_EMAIL = EMAIL_HOST_USER

ADMINS = [
    ('WIB Challenge', EMAIL_HOST_USER)
]

MANAGERS = ADMINS
