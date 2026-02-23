import os

import dj_database_url
from decouple import config

from .base import *

DEBUG = config('DEBUG', default=False, cast=bool)

SECRET_KEY = config('SECRET_KEY')

# Configuration de la base de données
DATABASES['default'] = dj_database_url.parse(config('DATABASE_URL'), conn_max_age=600, conn_health_checks=True)

if DATABASES['default']['ENGINE'] == 'django.db.backends.mysql':
    DATABASES['default']['OPTIONS'] = {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        'charset': 'utf8mb4',
    }

# Hôtes autorisés
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

# Détection de l'environnement Dokploy/Traefik
IS_TRAEFIK = config('TRAEFIK_ENABLED', default='traefik.me' in ''.join(ALLOWED_HOSTS), cast=bool)

# Configuration sécurité HTTPS
SSL_ENABLED = config('SECURE_SSL_ENABLED', default=False, cast=bool)

# Paramètres de sécurité avec granularité
if SSL_ENABLED:
    # Configuration HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)  # 1 an par défaut
    SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
    SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)

    # Si Dokploy/Traefik gère la redirection HTTPS, on peut désactiver celle de Django
    SECURE_SSL_REDIRECT = False if IS_TRAEFIK else config('SECURE_SSL_REDIRECT', default=True, cast=bool)

    # Sécurisation des cookies
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)

    # Protection additionnelle
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
else:
    # Configuration non-SSL
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Configuration CORS
CORS_ALLOW_CREDENTIALS = True

# Si l'environnement est Dokploy avec Traefik, on peut être plus permissif avec CORS
if IS_TRAEFIK:
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r'^https?://.*\.traefik\.me$',
    ]
else:
    CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', cast=lambda v: [s.strip() for s in v.split(',')])

# Add security logging
LOGGING['handlers']['security_file'] = {
    'level': 'WARNING',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': '/app/logs/security.log',
    'maxBytes': 1024 * 1024 * 5,  # 5 MB
    'backupCount': 5,
    'formatter': 'verbose',
}

LOGGING['loggers']['django.security']['handlers'].append('security_file')

# Performance logging
LOGGING['loggers']['django.db.backends'] = {
    'handlers': ['file'],
    'level': 'WARNING',
    'propagate': False,
}

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
#EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.ionos.com')
EMAIL_PORT = config('EMAIL_PORT', cast=int, default=587)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER
CONTACT_EMAIL = EMAIL_HOST_USER

ADMINS = [
    ('WIB Challenge', EMAIL_HOST_USER)
]

# Désactivation de Redis si la configuration n'est pas disponible
REDIS_ENABLED = config('REDIS_ENABLED', default='REDIS_URL' in os.environ, cast=bool)
if REDIS_ENABLED:
    REDIS_URL = config('REDIS_URL')
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'IGNORE_EXCEPTIONS': True,
                'PARSER_CLASS': 'redis.connection.HiredisParser',
                'CONNECTION_POOL_KWARGS': {'max_connections': 100}
            },
            'KEY_PREFIX': 'wib_challenge'
        }
    }
    CACHE_TTL = 60 * 15  # 15 minutes
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
