#!/bin/bash

set -e

echo "=========================================="
echo "Initialisation de WIB Challenge Backend"
echo "=========================================="

# Attendre que la base de données soit prête
echo "Attente de la base de donnees..."
python manage.py migrate --noinput

# Creer le superutilisateur par defaut si necessaire
echo "Verification du superutilisateur..."
python manage.py create_default_admin || echo "Superutilisateur existe deja"

# Initialiser les donnees de base
echo "Initialisation des donnees de base..."
python manage.py initialize || echo "Donnees de base deja initialisees"

# Peupler la base de donnees educatives
echo "Peuplement de la base de donnees educatives..."
python manage.py seed_education_data || echo "Donnees educatives deja peuplees"

# Creer les parametres par defaut
echo "Creation des parametres par defaut..."
python manage.py create_default_settings || echo "Parametres par defaut existent"

echo "=========================================="
echo "Initialisation terminee avec succes!"
echo "=========================================="

# Demarrer le serveur
exec python manage.py runserver 0.0.0.0:8000