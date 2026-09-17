### Parcours scolaire

Après connexion, le personnel scolaire est envoyé vers son tableau de bord. Il
peut créer les comptes des élèves de ses classes, créer une épreuve, sélectionner
les questions, puis la publier. L'élève se connecte avec le compte créé par son
enseignant et ne voit que les épreuves publiées pour sa classe.

Une tentative est limitée par la période de l'épreuve, sa durée et le nombre de
tentatives autorisées. Les QCM sont corrigés automatiquement ; les réponses
ouvertes apparaissent dans la file de copies à corriger. L'enseignant publie
ensuite les notes, et l'élève ne les voit qu'après cette publication.

Les noms de classes et de matières sont libres : le module peut donc être utilisé
par des établissements francophones ou anglophones. Les traductions de l'interface
peuvent être ajoutées séparément sans modifier les données ni le recrutement.
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

## Module scolaire

Le module scolaire est séparé du parcours de recrutement. Le super administrateur
crée les comptes du personnel dans l'administration Django, puis les rattache à
un établissement via **Personnel scolaire** :

- **Responsable d'établissement** : gère les classes, élèves, matières et épreuves de son établissement.
- **Enseignant** : gère les épreuves de son établissement, sans accès à sa structure administrative.

Les épreuves scolaires sont enregistrées avec une classe, une matière, une période,
une durée, un nombre maximal de tentatives et un barème sur 20 ou 100. Le personnel
scolaire ne peut pas accéder aux candidats ni aux résultats du module recrutement.

La structure scolaire peut être initialisée automatiquement au déploiement avec
les variables `EDUCATION_*`. Si `EDUCATION_SCHOOL_NAME` est vide, aucune école
n'est créée. Les élèves et le personnel scolaire sont exclus des listes du réseau
professionnel de recrutement.

