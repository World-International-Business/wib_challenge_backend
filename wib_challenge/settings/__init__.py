from decouple import config

if config('DEBUG', default=True, cast=bool):
    from .development import *
else:
    from .production import *
