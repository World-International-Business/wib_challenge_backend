# Prompt frontend — WIB Challenge (backend Django/DRF)

Tu es un développeur frontend senior. Construis le frontend de la plateforme WIB Challenge en consommant l'API backend décrite ci-dessous.

## Contexte

- Backend : Django + Django REST Framework, JWT auth.
- Base URL dev : `http://localhost:8000/api/` (adapter selon l'environnement).
- Doc OpenAPI interactive : `GET /api/docs/swagger/` et `GET /api/schema/` — utilise-la comme référence si un doute subsiste sur un champ.
- Langue UI : **français**.
- Deux types d'utilisateurs : **candidat** (rôle `developer`) et **recruteur/organisation** (rôle `organization`, lié à une `Organization`). Un utilisateur ne voit que ses propres ressources ; un recruteur voit celles de son organisation.

## 1. Authentification

| Méthode | Endpoint | Body |
|---|---|---|
| Inscription | `POST /api/auth/register/` | `{email, password, first_name, last_name, ...}` |
| Login | `POST /api/auth/login/` | `{email, password}` → `{access, refresh, user}` |
| Refresh | `POST /api/auth/token/refresh/` | `{refresh}` |
| Verify | `POST /api/auth/token/verify/` | `{token}` |
| Logout | `POST /api/auth/logout/` |
| Forgot password | `POST /api/auth/forgot-password/` |

Headers : `Authorization: Bearer <access>`. Implémente un intercepteur axios/fetch qui refresh automatiquement sur 401.

## 2. Espace recruteur — assistant Wiba (émission de besoin)

C'est le cœur produit : un chat conversationnel qui collecte le besoin de recrutement et produit une fiche de poste.

### Endpoints

- `GET /api/jobs/offer-conversations/` — liste des brouillons de l'utilisateur
- `POST /api/jobs/offer-conversations/` — crée une conversation ; body optionnel `{content: "premier message"}` pour que Wiba réponde immédiatement
- `GET /api/jobs/offer-conversations/{id}/` — historique complet (messages + blocs)
- `DELETE /api/jobs/offer-conversations/{id}/` — supprime le brouillon
- `POST /api/jobs/offer-conversations/{id}/messages/` — `{content}` → réponse `{message: {role, blocks}, state}`
- `PATCH /api/jobs/offer-conversations/{id}/messages/{mid}/` — `{content}` modifie un message utilisateur, tronque la suite et régénère
- `POST /api/jobs/offer-conversations/{id}/approve/` → `{offer_id, status, channels}` : valide la fiche, crée + publie l'offre, lance la diffusion
- `POST /api/jobs/offer-conversations/{id}/messages/{mid}/speak/` → `audio/wav` (voix de Wiba, option `{voice}`)
- `POST /api/jobs/offers/{id}/publish/` et `POST /api/jobs/offers/{id}/distribute/` `{channels?}` — publication / relance diffusion hors conversation

### Rendu des messages assistant

Chaque message a `content` (markdown léger) et `blocks` typés :

- `{type: "text", content}` — texte
- `{type: "job_card", data}` — **fiche de poste** : `title, description, responsibilities, requirements, benefits, skills[], jobType, experienceLevel, location, remoteAllowed, salary, currency, applicationUrl, applicationEmail, featured, requiredDocuments[], posteTitle, expiresAt, companyName, companyLogo, technicalEvaluation{ id,title }, psychotechEvaluation{...}, personalityEvaluation{...}`
- `{type: "quick_replies", options[]}` — chips cliquables qui envoient le texte comme message utilisateur
- `{type: "confirmation", data:{offer_id}}` + `{type: "channel_plan", data:{channels[]}}` — après approbation
- `{type: "summary", data}` — résumé

`state` de la conversation : `collecting | clarifying | review | editing | approved | publishing | published`. Affiche un indicateur de statut ; quand `state === 'review'` et qu'un `job_card` existe, propose le bouton **"Valider et publier"** → `approve/`.

Comportement attendu : Wiba pose 1-2 questions à la fois (`questions` dans la réponse LLM, intégrées au texte), propose des `quick_replies`, puis génère une fiche complète auto-remplie. Prévois un état de chargement (réponse synchrone, quelques secondes) et la gestion des erreurs `ai_rate_limited` (429), `ai_not_configured` (503), etc.

### Diffusion (retour de `approve` / `publish`)

`channels[]` = `{name, state, error?, url?}`. États possibles : `published`, `failed` (ex. LinkedIn non connecté, Emploi.cm non renseigné), `pending`. Affiche le résultat par canal honnêtement — ne jamais afficher "publié" pour un canal `failed`.

## 3. Espace recruteur — pipeline de recrutement

### Liste des offres et candidatures

- `GET /api/jobs/offers/` — offres de l'org + publiées ; filtres `status`, search
- `GET /api/jobs/offers/{id}/applications/` → `{statistics: {total, pending, shortlisted, accepted, rejected}, applications[]}`
- `GET /api/jobs/applications/organization/` — toutes les candidatures de l'org (filtres `job_offer`, `source`, `search`)
- `GET /api/jobs/applications/{id}/decision-options/` → `{status, version, allowed_statuses, reason_required_for}` — **utilise `version` comme `expected_version`** dans update-status pour éviter les conflits (409 `stale_decision`)
- `GET /api/jobs/applications/{id}/decision-history/` — journal des décisions
- `GET /api/jobs/applications/recruited/` — candidats acceptés

### Workflow d'une candidature (`PATCH /api/jobs/applications/{id}/update-status/`)

Body : `{status, reason?, recruitment_details?, expected_version?}`

Transitions autorisées : `pending → shortlisted|rejected`, `shortlisted → pending|accepted|rejected`, `accepted → pending`, `rejected → pending`.
`reason` **obligatoire** pour `accepted`, `rejected`, `pending`. `recruitment_details` (texte : date de prise de poste, conditions…) conseillé pour `accepted`.

### Évaluations

- `POST /api/jobs/applications/{id}/assign-evaluations/` — assigne les 3 évaluations configurées sur l'offre (technique/psychotech/personnalité), crée les invitations et envoie les emails. **400 si l'offre n'a pas les 3 évaluations.**
- `GET /api/jobs/applications/{id}/evaluation-results/` → `{evaluations: [{title, type, status, score, maxScore, averageOn20, completedAt}], globalScore}` — `status`: `assigned|started|completed`.
- `PATCH /api/jobs/applications/{id}/assign-evaluation/` `{evaluation_id}` — assignation unitaire alternative.

### Entretien (booking public par lien tokenisé)

- `POST /api/jobs/applications/{id}/interview-booking/` `{slots: [{starts_at, ends_at}, ...]}` (max 30, ≤8h, futurs, non chevauchants) → `{token, expires_at, booking_id}`
- Le candidat (ou le RH pour prévisualiser) utilise ensuite les endpoints **publics** :
  - `GET /api/jobs/interview-slots/{token}/` → `{slots: [{id, starts_at, ends_at}], booked, expires_at}`
  - `POST /api/jobs/interview-slots/{token}/book/` `{slot_id}` → réserve, remplit `interview_date`/`interview_duration` sur la candidature
- `PATCH /api/jobs/applications/{id}/schedule-interview/` `{interview_date, interview_duration, interview_link, interview_type, interview_notes}` — planification directe alternative.

### Page "Validations RH" (intervention humaine)

Le backend ne prend **jamais** de décision de recrutement automatique : l'analyse IA (`analyze_job_application`) remplit `ai_analysis`/`ai_decision`/`match_score` mais signale toujours `needs_human_review=True` avec `review_reason` pour que l'humain décide. Une notification email part aussi au RH (`hrAlertEmail` → email du compte → `Organization.email`).

Champs clés sur chaque candidature : `needs_human_review`, `review_reason`, `review_generation`, `decision_version`.

Endpoints dédiés (`/api/jobs/applications/{id}/…`) :

- `GET /decision-options/` → `{status, version, allowed_statuses, reason_required_for: ["accepted","rejected","pending"]}`
- `POST /human-review/` `{reason}` — marque le dossier comme nécessitant une intervention humaine
- `DELETE /human-review/` `{reason}` — lève le flag. ⚠️ Le body d'un DELETE est souvent ignoré par les clients HTTP ; envoyer la raison en query param `DELETE /human-review/?reason=...` ou en body (`axios.delete(url, {data:{reason}})`)
- Changer le statut via `update-status/` lève automatiquement `needs_human_review` quand la décision est prise.

Règles `update-status` : `reason` obligatoire pour `accepted`/`rejected`/`pending` (400 sinon) ; `expected_version` doit correspondre à `decision_version` courant sinon 409 `stale_decision` → recharger le dossier et réessayer.

### Contrat de travail

- `POST /api/jobs/applications/{id}/contract/prepare/` — multipart `contract_file` (PDF)
- `POST /api/jobs/applications/{id}/contract/send/` → `{status, token, expiresAt, contractUrl}` — envoie l'email au candidat, statut `sent`
- **Page publique candidat** (pas d'auth) :
  - `GET /api/jobs/contract/{token}/` → `{jobTitle, candidate, contractStatus, expiresAt, contractFileUrl}`
  - `POST /api/jobs/contract/{token}/request-otp/` → envoie un code à 6 chiffres par email (`{status: 'sent', expires_in: 600}`) ; throttlé 20/min et renvoie 429 si <60s entre envois
  - `POST /api/jobs/contract/{token}/verify-otp/` `{code}` → `{verified: true}` (5 tentatives max)
  - `POST /api/jobs/contract/{token}/upload-signed/` — multipart `signed_contract_file` (PDF ≤5 Mo, doit commencer par `%PDF-`) → `{status: 'signed'}` ; **403 sans OTP vérifié** (<15 min)

Statuts contrat : `not_prepared | sent | signed | rejected | expired`.

## 4. Espace candidat

- `POST /api/jobs/offers/{id}/apply/` — multipart : `applicant_name`, `applicant_email`, `cover_letter`, `resume` (PDF obligatoire OU `use_profile=true`), + un fichier `document_<type>` par doc dans `requiredDocuments` de l'offre (`portfolio`, `diploma`, `id_card`, …). Erreurs 409 : offre fermée, déjà candidat, propre offre.
- `GET /api/jobs/applications/me/` — mes candidatures
- `GET /api/jobs/offers/`, `GET /api/jobs/offers/slug/{slug}/`, `GET /api/jobs/offers/featured/`, `GET /api/jobs/offers/recent/`, `GET /api/jobs/search/`, `GET /api/jobs/metadata/`
- Page publique de réservation d'entretien et de signature de contrat (voir §3) — **sans login**.
- Notifications : `GET /api/organizations/notifications/` (vérifier le préfixe exact dans `/api/schema/`).

## 5. Maquettes d'écrans à prévoir

**Recruteur**
1. Liste des offres + statut de diffusion par canal
2. Chat Wiba (bulles messages, rendu `job_card`, quick replies, bouton vocal 🔊, approbation)
3. Kanban/list candidatures par statut avec stats
4. Fiche candidature : analyse IA, évaluations (scores), entretien, contrat
5. Paramètres organisation : `preferredChannels`, `linkedinPageUrl`, `emploiCmAccount`, `hrAlertEmail`

**Candidat**
6. Catalogue d'offres + page détail + formulaire de candidature (upload CV + docs requis dynamiques)
7. Mes candidatures (statut, convocation entretien, évaluations assignées)
8. Pages publiques : réservation créneau, consultation/signature contrat + OTP

## 6. Contraintes UX

- Afficher les erreurs API telles quelles (`detail`, `error`, `code`) — les codes métier (`conversation_closed`, `stale_decision`, `JOB_OFFER_CLOSED`, `APPLICATION_ALREADY_EXISTS`…) doivent avoir un message utilisateur clair.
- Jamais de statut "publié" côté canal sans confirmation backend.
- Temps réel non requis : polling ou refetch après chaque action suffit.
- Le TTS Wiba (`speak/`) retourne `audio/wav` — prévois un player et un fallback si 503.

Commence par explorer `GET /api/schema/` pour valider les schémas exacts avant de coder les écrans critiques (chat Wiba et pipeline candidature).
