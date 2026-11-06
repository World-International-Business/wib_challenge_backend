#!/bin/bash

set -e

echo "=========================================="
echo "Initialisation de WIB Challenge Backend"
echo "=========================================="

# Attendre que la base de données soit prête
echo "Attente de la base de donnees..."
until python manage.py migrate --noinput; do
  echo "La base de donnees n'est pas encore prete - attente..."
  sleep 2
done

# Creer les parametres applicatifs necessaires
echo "Creation des parametres par defaut..."
python manage.py create_default_settings

# Creer le superutilisateur uniquement si les secrets sont fournis par l'environnement.
if [ -n "${ADMIN_EMAIL:-}" ] && [ -n "${ADMIN_PASSWORD:-}" ]; then
  echo "Verification du superutilisateur..."
  python manage.py create_default_admin
fi

# Initialiser la structure scolaire uniquement si elle est configuree.
if [ -n "${EDUCATION_SCHOOL_NAME:-}" ]; then
  echo "Initialisation de la structure scolaire..."
  python manage.py initialize_education
fi

# Collecter les fichiers statiques
echo "Collecte des fichiers statiques..."
mkdir -p collected_static
python manage.py collectstatic --noinput --clear

echo "=========================================="
echo "Initialisation terminee avec succes!"
echo "=========================================="

# Demarrer le serveur de production
exec gunicorn wib_challenge.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" --timeout "${GUNICORN_TIMEOUT:-120}"