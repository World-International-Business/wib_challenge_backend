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

En production, `PUBLIC_SITE_URL` doit contenir l'URL publique complète du site.
Elle est utilisée dans les emails envoyés aux candidats :

```env
PUBLIC_SITE_URL=https://tests-evaluations.worldwide-international.business
```

Pour activer l'envoi SMTP avec Gmail en développement, renseigner dans `.env` :

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=adresse@gmail.com
EMAIL_HOST_PASSWORD=mot_de_passe_d_application
DEFAULT_FROM_EMAIL=adresse@gmail.com
```

Le mot de passe d'application doit rester uniquement dans `.env` ou dans les
variables secrètes de l'environnement de déploiement. Ne pas le committer.

Les variables `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_FROM` et `SMTP_USE_TLS` sont également acceptées en développement.

Après avoir migré la base de données, créer un super utilisateur et les paramètres par défaut

```bash
  python manage.py makemigrations
  python manage.py migrate
  python manage.py createsuperuser
  python manage.py create_default_settings
```

