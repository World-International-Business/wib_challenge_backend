try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except Exception:
    # Celery est optionnel : ne pas bloquer Django si la dépendance n'est pas installée
    celery_app = None
    __all__ = ()