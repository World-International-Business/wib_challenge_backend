# WIB Challenge

## Installation

Après avoir cloné le projet, et créé un environnement virtuel, installer les dépendances avec la commande suivante :

```bash
  pip install -r requirements.txt
```

## Setup

Copier le fichier `.env.example` en `.env` et remplir les variables d'environnement

```bash
cp .env.example .env
```

Après avoir migré la base de données, créer un super utilisateur et les paramètres par défaut

```bash
  python manage.py makemigrations
  python manage.py migrate
  python manage.py createsuperuser
  python manage.py create_default_settings
```

