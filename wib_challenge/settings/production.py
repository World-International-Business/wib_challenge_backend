import dj_database_url
from decouple import config

from .base import *

DEBUG = False

SECRET_KEY = config('SECRET_KEY')

DATABASES['default'] = dj_database_url.parse(config('DATABASE_URL'), conn_max_age=600, conn_health_checks=True)

if not DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default']['OPTIONS'] = {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        'charset': 'utf8mb4',
    }

# # Configuration du cache Redis
# REDIS_URL = config('REDIS_URL', default='redis://redis:6379/0')

# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': REDIS_URL,
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#             'SOCKET_CONNECT_TIMEOUT': 5,
#             'SOCKET_TIMEOUT': 5,
#             'IGNORE_EXCEPTIONS': True,
#             'PARSER_CLASS': 'redis.connection.HiredisParser',
#             'CONNECTION_POOL_KWARGS': {'max_connections': 100}
#         },
#         'KEY_PREFIX': 'wib_challenge'
#     }
# }

# CACHE_TTL = 60 * 15  # 15 minutes

# # Cache des sessions
# SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
# SESSION_CACHE_ALIAS = 'default'

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])


# Security settings for HTTPS
if config('SECURE_SSL_ENABLED', default=False, cast=bool):
    SECURE_HSTS_SECONDS = 31536000  # 1 year - recommended value for production
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', cast=lambda v: [s.strip() for s in v.split(',')])
CORS_ALLOW_CREDENTIALS = True

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER

ADMINS = [
    ('WIB Challenge', EMAIL_HOST_USER)
]
