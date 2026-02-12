import os

from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wib_challenge.settings.base')

app = Celery('wib_challenge')

# Charger la configuration depuis les settings Django avec le namespace CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discovery des tasks dans les apps (tasks.py)
app.autodiscover_tasks()
