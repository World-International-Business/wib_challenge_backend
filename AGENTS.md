# Agent Notes – WIB Challenge Backend

## Commands de vérification

```powershell
python manage.py check
python manage.py check --deploy --settings=wib_challenge.settings.production
python manage.py test apps.learning apps.payments --keepdb
python manage.py test apps.jobs --noinput
python manage.py test apps.jobs.test_agent_api --noinput
python manage.py test apps.jobs.test_offer_generation --noinput
python manage.py send_review_notifications
python manage.py seed_courses --force
python manage.py makemigrations --check --dry-run
```

Sur le poste Windows local, utiliser `env\Scripts\python.exe` à la place de `python` pour ces commandes : cet environnement contient les dépendances Django.

## Réception automatique des candidatures email

- API JWT propriétaire uniquement : `GET/POST /api/email-inboxes/`, `GET/PATCH /api/email-inboxes/{id}/`, `POST .../{id}/test/`, `POST .../{id}/sync/`, `GET .../{id}/messages/`, `POST .../{id}/messages/{mid}/assign/` (`offerId`), `GET .../{id}/messages/{mid}/resume/`, `GET .../{id}/messages/{mid}/original/`.
- Deux modes de connexion de boîte : **IMAP TLS 993** (`POST /api/email-inboxes/` : `host`, `username`, `password` write-only, `folder` ASCII ; créer désactivé, tester, PATCH `enabled=true`) et **Gmail OAuth** (`POST /api/email-inboxes/gmail-connect/` : `code`, `redirect_uri` optionnel, `folder` = libellé Gmail, `defaultOffer`, `enabled`) — le consentement frontend doit utiliser `access_type=offline`, `prompt=consent` et le scope `gmail.readonly`. Une boîte Gmail est aussi auto-connectée quand le login OAuth (`GoogleAuthCodeSerializer`) ramène un refresh token avec ce scope (`connect_gmail_from_login`). `provider` distingue les deux modes ; `oauth_secret` chiffre le refresh token. Microsoft/Outlook non pris en charge.
- Utiliser un dossier de candidatures dédié. L’import lit aussi les messages déjà lus, sans modifier les flags ni déplacer/supprimer les emails. Premier passage : historique du dossier, par lots de 25. UIDVALIDITY/UID et empreinte du contenu empêchent les réimports.
- Sans offre certaine ou avec une référence à une autre organisation : message `unassigned`, rattachement humain requis. `defaultOffer` est utilisé seulement en l’absence de référence JOB explicite ; les offres fermées/expirées ne sont pas sélectionnées automatiquement.
- Message max 10 Mo ; CV PDF max 5 Mo/50 pages. Pièce jointe absente, ambiguë ou inexploitable : dossier conservé et revue humaine requise. Original `.eml` chiffré conservé ; les messages dépassant 10 Mo restent dans la boîte source avec une erreur visible. Messages automatiques/listes/notifications de la plateforme ignorés pour prévenir les boucles.
- CV email hors médias publics : `EMAIL_RESUME_ROOT` (défaut `private_uploads/email_resumes`), partagé entre web et worker. Téléchargements JWT en Blob côté frontend, jamais un lien public direct. Secrets et originaux réutilisent le chiffrement des canaux : garder la même clé entre les services et les déploiements.
- `autoAnalyzeApplications` pilote la file d’analyse email persistante (indépendante du drapeau web `USE_CELERY_FOR_CV_ANALYSIS`). Reprises avec backoff, maximum 5 tentatives ; les erreurs finales nécessitent une revue humaine. Aucune décision de refus automatique. `notifyBlockingCases` conserve son rôle sur le système d’alertes existant.
- Celery Beat : synchronisation toutes les 60 s, traitement de la file d’analyse toutes les 30 s. Nécessite un worker et une seule instance Beat, la même base PostgreSQL/MySQL, le même broker (`REDIS_URL` ou `CELERY_BROKER_URL`), la même clé de chiffrement et le même volume privé que le web.
- Profil Docker optionnel `email` : Redis interne sans port publié, worker et Beat. Avant activation, configurer le broker commun (Redis inclus : `redis://email-redis:6379/0`) dans le gestionnaire de secrets, sans changer les secrets depuis le code. `docker compose --profile email up -d --build`. Ne pas activer un deuxième Beat si Dokploy en gère déjà un.
- Préflight : `python manage.py check_email_pipeline --require-shared-database --broker` après migrations. Le préflight vérifie base/migrations/chiffrement/stockage privé/broker, pas la connectivité d’une boîte ni la présence d’un worker.
- Sans broker, exécution administrative contrôlée : `python manage.py import_email_applications --organization <id> --inbox <id> --analyze`. Sans `--analyze`, import uniquement. Cette commande peut traiter de vrais emails et appeler l’IA ; ne pas l’exécuter sur une boîte réelle sans autorisation.
- Ancien endpoint `POST /api/jobs/applications/sync-email-applications/` : désormais demande asynchrone limitée aux connexions activées/vérifiées du compte (`202`, ou `400` sans connexion, `503` si broker indisponible). Il ne lit plus la boîte IMAP globale.
- Vérification : `python manage.py test apps.jobs.test_email_pipeline --noinput`, puis `python manage.py test apps.jobs --noinput`. Les tests IMAP/IA utilisent des doubles contrôlés, pas une messagerie ni un fournisseur IA réels.

## Variables d'environnement critiques en production

- `SECRET_KEY` : > 50 caractères, ne commençant pas par `django-insecure-`.
- `DEBUG=False`
- `ALLOWED_HOSTS` : liste sans scheme (`exemple.com,127.0.0.1`).
- `CSRF_TRUSTED_ORIGINS` et `CORS_ALLOWED_ORIGINS` : avec `https://`.
- `DATABASE_URL` : PostgreSQL de préférence (`postgres://...` ou `postgresql://...`).
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` / `GOOGLE_OAUTH_REDIRECT_URI` (liste séparée par virgules : `http://localhost:5173/auth/google/callback,https://recrutement.worldwide-international.business/auth/google/callback`) : login Google (ID token + authorization code).
- `GENAI_API_KEY` : clé Gemini, à configurer sans la journaliser.
- `GEMINI_OFFER_MODEL` : modèle de génération d’offres, défaut `gemini-3.5-flash-lite`. Cette variable ne change pas les modèles des autres services IA.
- `PAYMENT_WEBHOOK_BASE_URL`, `CINETPAY_*`, `STRIPE_*`, `PAYPAL_*` : fournies via Dokploy / secrets manager.
- `AWS_*` ou `PRIVATE_STORAGE_BACKEND=local` : pour contenus et certificats privés.
- `TRAEFIK_ENABLED=True` et `SECURE_SSL_REDIRECT=False` quand Traefik gère HTTPS.

## Agent conversationnel d'émission de besoin

- `GET/POST /api/jobs/offer-conversations/` — liste des brouillons / création (`content` optionnel = premier message).
- `GET/DELETE /api/jobs/offer-conversations/{id}/` — historique complet (messages + blocs) / suppression.
- `POST /api/jobs/offer-conversations/{id}/messages/` — envoi message utilisateur → réponse agent `{message:{role,blocks},state}`.
- `PATCH /api/jobs/offer-conversations/{id}/messages/{mid}/` — modifier un message utilisateur : tronque la suite et régénère.
- `POST /api/jobs/offer-conversations/{id}/approve/` — crée l'offre, la publie et diffuse → `{offerId,status,channels}`.
- `POST /api/jobs/offers/{id}/publish/` — publication + diffusion → `{status,channels,offer}`.
- `POST /api/jobs/offers/{id}/distribute/` — relance diffusion (`channels` optionnel).
- Blocs assistant : `text`, `job_card`, `quick_replies`, `confirmation`, `channel_plan`.
- Canaux réellement branchés : `site_carriere` (réel). `linkedin`/`emploi_cm` = stubs (activés par `LINKEDIN_API_TOKEN`/`EMPLOI_CM_API_TOKEN`, sinon état `failed` "non configuré"). Jamais `published` sans confirmation du canal.
- `Organization.preferred_channels` (API : `preferredChannels`) pilote la diffusion ; `site_carriere` est toujours inclus. `linkedinPageUrl`/`emploiCmAccount` requis côté org pour ces canaux. `hrAlertEmail` reçoit les alertes needsHumanReview (fallback : email du compte puis `Organization.email`).
- Audit : `AgentEvent` `offer_agent.reply` / `offer.approved` ; modèle `OFFER_AGENT_MODEL` dans `services/offer_agent.py`.

## Paiements

- `POST /api/payments/course-checkout/` : prix calculé côté serveur.
- `POST /api/payments/webhooks/<provider>/` : signature vérifiée, idempotent.
- Les statuts `succeeded` activent `CourseEnrollment` automatiquement.

## Certificats

- `GET /api/learnings/courses/{id}/certificate/eligibility/`
- `GET /api/certificates/me/`
- `GET /api/certificates/{id}/`
- `POST /api/certificates/{id}/checkout/`
- `POST /api/certificates/{id}/issue/`
- `GET /api/certificates/{id}/download/`
- `GET /api/certificates/verify/{verification_code}/`
- Numéro non prédictible (`WIB-{année}-{compteur}`) + code de vérification aléatoire.

## Profil / CV

- `GET/POST/DELETE /api/candidate-profiles/me/resume/` (PDF, max 5 Mo)
- `GET /api/candidate-profiles/me/dashboard/`
- `GET /api/candidate-profiles/me/certificates/`
- `GET /api/candidate-profiles/me/cv-data/`

## Authentification

- `POST /api/auth/register/`
- `POST /api/auth/login/` (JWT access + refresh)
- `POST /api/auth/token/refresh/`
- `POST /api/auth/token/verify/`
- `POST /api/auth/logout/`
- `POST /api/auth/forgot-password/`
- `GET/POST /api/users/` (profil utilisateur)

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
6. Si le catalogue est vide, exécuter dans la console conteneur :
   ```bash
   python manage.py seed_courses --force
   ```
7. La documentation OpenAPI est disponible en production :
   - `GET /api/schema/`
   - `GET /api/docs/swagger/`
   - `GET /api/docs/redoc`

## Écarts connus

- Les fournisseurs CinetPay/Stripe/PayPal sont des stubs configurables : remplacer `providers.py` par des appels HTTP réels.
- `certificate_generator.py` utilise PyMuPDF (`fitz`); vérifier que `PyMuPDF` est bien installé en production.
- Le téléchargement de certificat retourne une URL temporaire statique : utiliser des signed URLs S3 quand `PRIVATE_STORAGE_BACKEND=aws`.
- OpenAPI contient des warnings drf_spectacular sur `EvaluationQuestionProportions` et des conflits d'enum : non bloquants.

## Pipeline email en production Dokploy

- Le service backend actuel suit la branche `dev_back`.
- Activer le profil `email` avec `docker-compose.yml` et `docker-compose.dokploy.yml`. La surcharge donne aux workers accès au réseau externe `dokploy-network` de la base partagée, sans modifier la configuration locale.
- Dans le champ de commande personnalisée Dokploy, commencer par `compose` et non `docker compose` : Dokploy préfixe lui-même `docker`. Ajouter `--profile email` et les deux fichiers `-f`, puis `up -d --build`, en conservant le nom de projet généré par Dokploy.
- `REDIS_URL`, `CELERY_BROKER_URL` et `CELERY_RESULT_BACKEND` doivent désigner le broker réellement accessible ; le profil fournit `email-redis` sur le port interne 6379. Ne pas publier ce port.
- Le web et le worker doivent partager la base, les secrets de chiffrement existants et le volume privé des CV. Ne pas renouveler ces secrets pour résoudre une erreur de connexion.
- Vérifier `python manage.py check_email_pipeline --require-shared-database --broker` avant le démarrage de Celery et conserver une seule instance de Beat. Ce contrôle ne lit pas de boîte et n’envoie aucun email.
- Tests ciblés : `python manage.py test apps.jobs.test_email_pipeline --noinput`. Un HTTP 202 de synchronisation confirme uniquement la mise en file, pas l’import ni l’analyse.

## Filtre commun des candidatures email

- Avant création d’un dossier, `services/recruitment_email.py` exige un objet indiquant une candidature, un message renseigné hors signature/liens/citations et un PDF exploitable. Le HTML est converti en texte sans exécuter scripts ni styles.
- Les emails incomplets restent chiffrés et consultables : `status=incomplete`, `analysisState=manual`, motif dans `errorCode`, sans dossier créé, analyse, refus ni email automatique de relance. Le candidat doit renvoyer les éléments manquants ; aucun original n’est modifié.
- L’offre doit être publiée, non expirée et appartenir à l’organisation. Le titre dans l’objet est comparé sans distinction de casse ni d’accents ; les références JOB/ORG restent prises en charge. Un poste ambigu nécessite un rattachement humain ; l’offre par défaut ne sert à départager que des offres portant le même titre explicite.
- Le rattachement manuel réapplique les contrôles et ne permet pas d’importer un message incomplet ni d’affecter une offre fermée. Les dossiers historiques ne sont pas supprimés ou reclassés rétroactivement.
- PDF : maximum 5 Mo et 50 pages, non chiffré, non vide, sans fichiers embarqués ; les scans PDF restent utilisables par le traitement OCR existant. Ce contrôle technique n’est pas un antivirus ni une certification du contenu du CV.
- Les consignes contenues dans les CV ne modifient pas les règles déterministes du filtre. L’analyse IA reçoit aussi une instruction système de traiter les documents candidats comme des données non fiables ; toute décision finale demeure humaine.
