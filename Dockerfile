FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=wib_challenge.settings.production

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copie du projet
COPY . .

# Création d'un utilisateur non-privilégié pour exécuter l'application
RUN adduser --disabled-password --gecos "" django
RUN chown -R django:django /app
USER django

# Création des dossiers pour les fichiers statiques et médias
RUN mkdir -p /app/static /app/media

RUN python manage.py makemigrations accounts candidates core evaluations organizations questions

# Collecte des fichiers statiques
RUN python manage.py collectstatic --noinput

# Exécution de l'application
CMD ["sh", "-c", "python manage.py wait_for_db && python manage.py migrate && gunicorn wib_challenge.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
