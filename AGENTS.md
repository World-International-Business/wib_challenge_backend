# Agent Notes – WIB Challenge Backend

## Commands de vérification

```powershell
python manage.py check
python manage.py check --deploy --settings=wib_challenge.settings.production
python manage.py test apps.learning apps.payments --keepdb
python manage.py makemigrations --check --dry-run
```

## Variables d'environnement critiques en production

- `SECRET_KEY` : > 50 caractères, ne commençant pas par `django-insecure-`.
- `DEBUG=False`
- `ALLOWED_HOSTS` : liste sans scheme (`exemple.com,127.0.0.1`).
- `CSRF_TRUSTED_ORIGINS` et `CORS_ALLOWED_ORIGINS` : avec `https://`.
- `DATABASE_URL` : PostgreSQL de préférence (`postgres://...` ou `postgresql://...`).
- `PAYMENT_WEBHOOK_BASE_URL`, `CINETPAY_*`, `STRIPE_*`, `PAYPAL_*` : fournies via Dokploy / secrets manager.
- `AWS_*` ou `PRIVATE_STORAGE_BACKEND=local` : pour contenus et certificats privés.
- `TRAEFIK_ENABLED=True` et `SECURE_SSL_REDIRECT=False` quand Traefik gère HTTPS.

## Paiements

- `POST /api/payments/course-checkout/` : prix calculé côté serveur.
- `POST /api/payments/webhooks/<provider>/` : signature vérifiée, idempotent.
- Les statuts `succeeded` activent `CourseEnrollment` automatiquement.

## Certificats

- `GET /api/learnings/courses/{id}/certificate/eligibility/`
- `POST /api/certificates/{id}/checkout/`
- `POST /api/certificates/{id}/issue/`
- `GET /api/certificates/{id}/download/`
- `GET /api/certificates/verify/{verification_code}/`
- Numéro non prédictible (`WIB-{année}-{compteur}`) + code de vérification aléatoire.

## Profil / CV

- `GET/POST/DELETE /api/candidates/profiles/me/resume/` (PDF, max 5 Mo)
- `GET /api/candidates/profiles/me/dashboard/`
- `GET /api/candidates/profiles/me/cv-data/`

## Déploiement

1. Pousser la branche `dev` (ou `main`) sur le repo lié à Dokploy.
2. Dokploy reconstruit l'image et exécute `entrypoint.sh`.
3. `entrypoint.sh` lance `wait_for_db`, `migrate accounts`, `migrate` puis Gunicorn.
4. Si `python manage.py migrate` n'a pas été exécuté sur la base de production :
   - Ouvrir la console du conteneur sur Dokploy.
   - Exécuter :
     ```bash
     python manage.py showmigrations
     python manage.py migrate --noinput
     python manage.py showmigrations
     ```
5. Vérifier `GET http(s)://<host>/health/` et `GET /api/learnings/courses/`.

## Écarts connus

- Les fournisseurs CinetPay/Stripe/PayPal sont des stubs configurables : remplacer `providers.py` par des appels HTTP réels.
- `certificate_generator.py` utilise PyMuPDF (`fitz`); vérifier que `PyMuPDF` est bien installé en production.
- Le téléchargement de certificat retourne une URL temporaire statique : utiliser des signed URLs S3 quand `PRIVATE_STORAGE_BACKEND=aws`.
- OpenAPI contient des warnings drf_spectacular sur `EvaluationQuestionProportions` et des conflits d'enum : non bloquants.
