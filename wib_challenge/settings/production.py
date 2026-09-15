import os

import dj_database_url

from .base import *

DEBUG = False

SECRET_KEY = os.getenv('SECRET_KEY')

DATABASES['default'] = dj_database_url.config(conn_max_age=600, conn_health_checks=True)

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS').split(',')

# Derrière Traefik/Dokploy : le proxy termine le HTTPS et transmet
# X-Forwarded-Proto. Sans cela, request.is_secure() vaut False et la
# vérification CSRF rejette les POST venant de https://... (erreur 403).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Origines autorisées pour les requêtes POST (formulaires, admin...).
# Priorité à la variable d'env ; sinon dérivé d'ALLOWED_HOSTS en https.
_csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()] or [
    f'https://{host}' for host in ALLOWED_HOSTS if host not in ('*', '')
]

SECURE_HSTS_SECONDS = 0

SECURE_SSL_REDIRECT = False

SESSION_COOKIE_SECURE = False

CSRF_COOKIE_SECURE = False

SECURE_HSTS_INCLUDE_SUBDOMAINS = False

SECURE_HSTS_PRELOAD = False

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

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
