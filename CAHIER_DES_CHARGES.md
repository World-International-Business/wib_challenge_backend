# CAHIER DES CHARGES - WIB CHALLENGE

## Plateforme d'Évaluation et de Formation Professionnelle

---

## 📋 INFORMATIONS GÉNÉRALES

**Nom du Projet** : WIB Challenge  
**Version** : 1.0  
**Date** : Août 2025  
**Équipe** : World International Business  
**Type** : Application Web Full-Stack

### Objectif Principal

Développer une plateforme complète intégrant l'évaluation des compétences techniques, la formation professionnelle et le
recrutement dans un écosystème unifié.

---

## 🎯 VUE D'ENSEMBLE DU SYSTÈME

### Architecture Générale

La plateforme WIB Challenge est structurée autour de **3 modules principaux** interconnectés :

1. **📝 Module d'Évaluation Intelligent** - Tests et évaluations de compétences
2. **📚 Module d'Apprentissage (LMS)** - Formation et développement des compétences
3. **💼 Module de Recrutement** - Gestion des offres d'emploi et processus de recrutement

### Acteurs du Système

- **👤 Candidats/Professionnels** : Utilisateurs passant des tests, suivant des formations
- **🏢 Organisations** : Entreprises créant des évaluations et publiant des offres
- **👥 Candidats Externes** : Participants invités via liens sécurisés
- **⚙️ Administrateurs** : Gestionnaires de la plateforme

---

# 📝 MODULE 1 : SYSTÈME D'ÉVALUATION INTELLIGENT

## 1.1 Vue d'Ensemble

### Fonctionnalités Principales

- **Création d'évaluations personnalisées** : Tests sur mesure selon les besoins
- **Questions multichoix intelligentes** : Base de données riche et catégorisée
- **Génération automatique** : Tests créés selon le poste et le niveau
- **Invitations externes** : Accès sécurisé pour candidats non-inscrits
- **Correction automatique** : Résultats instantanés avec analyse détaillée

### Types d'Évaluations

- **Évaluations Techniques**
    - Langages de programmation (Python, JavaScript, Java, etc.)
    - Frameworks (React, Django, Angular, etc.)
    - Outils et méthodologies
- **Évaluations Logiques**
    - Tests de raisonnement
    - Résolution de problèmes
    - Pensée analytique
- **Tests de Personnalité**
    - Traits professionnels
    - Compatibilité culturelle
    - Style de management
- **Compétitions**
    - Challenges communautaires
    - Classements temps réel
    - Système de récompenses

### Système de Notation

- **Pondération intelligente** : Points selon difficulté et importance
- **Facteur temps** : Rapidité de résolution prise en compte
- **Distribution adaptative** :
    - Junior : 60% Facile, 30% Moyen, 10% Difficile
    - Intermédiaire : 30% Facile, 50% Moyen, 20% Difficile
    - Senior : 20% Facile, 40% Moyen, 40% Difficile

### Invitations Externes

- **Génération de tokens** : Liens sécurisés temporaires
- **Accès simplifié** : Pas d'inscription requise
- **Sécurité renforcée** : Une tentative unique par invitation
- **Traçabilité complète** : Suivi de tous les accès

---

## 📚 MODULE 2 : PLATEFORME D'APPRENTISSAGE (LMS)

### 2.1 Vue d'Ensemble

#### Fonctionnalités Principales

- **Cours structurés** : Parcours pédagogiques progressifs
- **Contenus multimédias** : Vidéos, PDF, liens, contenu markdown
- **Quiz interactifs** : Évaluations des connaissances avec feedback
- **Certificats** : Validation officielle des compétences acquises
- **Suivi des progrès** : Analytics détaillées et tableaux de bord

#### Structure Hiérarchique

```
Cours
├── Module 1
│   ├── Contenu 1 (Vidéo/PDF/Lien)
│   ├── Contenu 2
│   └── Quiz du Module
├── Module 2
└── Évaluation Finale
```

### 2.2 Types de Contenus

#### Formats Supportés

- **Vidéos** : Upload local + intégration YouTube/Vimeo
- **Documents PDF** : Visualisation intégrée + téléchargement optionnel
- **Ressources externes** : Articles, documentation, outils tiers
- **Contenu Markdown** : Rédaction directe enrichie

#### Types de Cours

- **Gratuits** : Accès libre pour tous
- **Payants** : Sur abonnement/achat
- **Niveaux** : Débutant, Intermédiaire, Avancé
- **Domaines** : Technique, Management, Soft Skills

### 2.3 Système d'Évaluation

#### Types de Quiz

- **Questions choix multiples** : Une seule bonne réponse
- **Questions réponses multiples** : Plusieurs réponses correctes
- **Questions vrai/faux** : Validation binaire
- **Feedback immédiat** : Explications détaillées après réponse

#### Configuration

- **Seuil de réussite** : Configurable (défaut 70%)
- **Tentatives** : Limitées ou illimitées selon le cours
- **Temps limite** : Optionnel par quiz
- **Randomisation** : Ordre aléatoire des questions/réponses

### 2.4 Certification et Suivi

#### Types de Certificats

- **Certificats de Module** : Validation par section
- **Certificats de Cours** : Completion complète
- **Certificats de Parcours** : Série de cours achevée

#### Critères d'Obtention

- **Completion 100%** de tous les contenus obligatoires
- **Réussite des quiz** avec score minimum requis
- **Participation** aux évaluations finales
- **Respect des délais** si applicable

#### Métriques de Suivi

- **Pourcentage de progression** par cours/module
- **Temps passé** sur chaque contenu
- **Scores détaillés** avec historique complet
- **Streak d'apprentissage** et régularité

---

## 💼 MODULE 3 : SYSTÈME DE RECRUTEMENT INTELLIGENT

### 3.1 Vue d'Ensemble

#### Fonctionnalités Principales

- **Gestion des offres d'emploi** : Publication et suivi des postes
- **Recherche avancée** : Filtres intelligents et matching sémantique
- **Analyse automatique des CV** : IA pour extraction et scoring
- **Processus intégré** : Workflow complet de recrutement
- **Dashboard recruteur** : Outils d'aide à la décision

#### Types de Contrats Supportés

- **CDI / CDD** : Contrats classiques
- **Stage / Alternance** : Formations professionnelles
- **Freelance** : Missions ponctuelles
- **Télétravail** : Postes distants

### 3.2 Gestion des Offres

#### Informations Requises

- **Descriptif du poste** : Titre, description, missions
- **Compétences techniques** : Technologies et outils requis
- **Niveau d'expérience** : Junior, Confirmé, Senior
- **Conditions** : Salaire, localisation, avantages
- **Critères de sélection** : Formation, langues, certifications

#### Catégorisation Automatique

- **Domaines professionnels** :
    - Développement informatique
    - Data Science / IA
    - Marketing Digital
    - Finance & Comptabilité
    - Ressources Humaines
    - Design & UX/UI

#### Statuts des Offres

- **Brouillon** : En cours de rédaction
- **Publiée** : Visible aux candidats
- **Expirée** : Date limite dépassée
- **Fermée** : Recrutement terminé

### 3.3 Intelligence Artificielle

#### Analyse Automatique des CV

- **Extraction d'informations** :
    - Expériences professionnelles
    - Formations et diplômes
    - Compétences techniques identifiées
    - Langues et niveaux
- **Scoring de compatibilité** : Pourcentage d'adéquation avec l'offre
- **Résumé automatique** : Points clés du profil candidat
- **Recommandations** : Suggestions d'amélioration

#### Matching Intelligent

- **Recherche sémantique** : Compréhension du contexte
- **Correspondance compétences** : Analyse fine des technologies
- **Scoring prédictif** : Probabilité de réussite du candidat
- **Classement automatique** : Tri par pertinence
- **Voir Plus** :
- https://claude.ai/share/481e04db-a4b4-4a5a-9319-61a66301ff9f
- https://chatgpt.com/share/68b975a2-4f00-800b-86cf-718d9ae9f77f
- https://grok.com/s/c2hhcmQtNA%3D%3D_b6cdf296-7fda-4470-9e5d-ad0f1b3f9201

### 3.4 Processus de Recrutement

#### Workflow Standard

1. **Publication d'offre** → Diffusion automatique
2. **Réception candidatures** → Notification temps réel
3. **Pré-screening IA** → Analyse et scoring automatique
4. **Évaluation technique** → Tests personnalisés optionnels
5. **Entretiens** → Planification et suivi
6. **Décision finale** → Feedback automatisé

#### Outils Recruteur

- **Dashboard candidatures** : Vue d'ensemble centralisée
- **Comparaison de profils** : Analyse côte à côte
- **Templates d'emails** : Réponses standardisées
- **Historique complet** : Traçabilité des échanges
- **Rapports analytics** : Métriques de performance

---

## 🔗 INTÉGRATION DES MODULES

### 4.1 Interactions Inter-Modules

#### Module Évaluation ↔ Module Recrutement

- **Tests de pré-sélection** : Évaluations automatiques lors des candidatures
- **Scores intégrés** : Résultats d'évaluation dans les candidatures
- **Invitations post-candidature** : Tests spécifiques après postulation

#### Module Apprentissage ↔ Module Évaluation

- **Certifications valorisées** : Prise en compte dans les évaluations
- **Recommandations formations** : Suggestions basées sur les résultats de tests
- **Parcours progressifs** : Formation → Test → Certification

#### Module Apprentissage ↔ Module Recrutement

- **Compétences certifiées** : Mise en avant dans les profils
- **Formations ciblées** : Recommandations basées sur les offres
- **Développement continu** : Suivi post-recrutement

### 4.2 Données Partagées

#### Base de Connaissances Unifiée

- **Technologies** : Référentiel unique pour tous les modules
- **Professions** : Classification standardisée
- **Domaines** : Structure hiérarchique partagée
- **Compétences** : Mapping unifié des skills

#### Profils Utilisateur Consolidés

- **Historique complet** : Évaluations, formations, candidatures
- **Progression globale** : Évolution des compétences dans le temps
- **Recommandations croisées** : Suggestions multi-modules

---

## 🎯 CAS D'USAGE PRINCIPAUX

### Parcours Candidat Standard

1. **Inscription** → Création de profil complet
2. **Formation** → Suivi de cours et certification
3. **Évaluation** → Tests de validation des compétences
4. **Recherche emploi** → Application aux offres correspondantes
5. **Recrutement** → Process avec tests et entretiens

### Parcours Candidat Externe

1. **Invitation reçue** → Email avec lien sécurisé
2. **Accès test** → Interface simplifiée sans inscription
3. **Passation** → Évaluation spécifique à l'organisation
4. **Résultats** → Feedback automatique au recruteur

### Parcours Organisation

1. **Création compte** → Profil entreprise
2. **Publication offres** → Gestion des postes
3. **Évaluations personnalisées** → Tests sur mesure
4. **Gestion candidatures** → Screening et suivi
5. **Décision finale** → Outils d'aide au choix

---

## 🏗️ ARCHITECTURE TECHNIQUE

### 5.1 Stack Technologique

#### Frontend

- **Framework** : React 18+ avec TypeScript
- **State Management** : Redux Toolkit + RTK Query
- **UI Library** : Material-UI (MUI) ou Ant Design
- **Routing** : React Router v6
- **Build Tool** : Vite.js pour performance optimisée
- **Testing** : Jest + React Testing Library

#### Backend

- **Framework** : Django 5.1+ avec Django REST Framework
- **Base de Données** : SQLite (dev) / PostgreSQL (prod)
- **Authentication** : JWT avec refresh tokens
- **API Documentation** : Swagger/OpenAPI avec drf-yasg
- **Task Queue** : Celery + Redis pour tâches asynchrones
- **File Storage** : Django Media + support AWS S3

#### Infrastructure

- **Containerization** : Docker + Docker Compose
- **Web Server** : Nginx comme reverse proxy
- **CORS** : Configuration stricte pour sécurité
- **Monitoring** : Logs centralisés + métriques
- **Déploiement** : Support CI/CD avec GitHub Actions

### 5.2 Architecture API

#### Design Patterns

- **RESTful API** : Endpoints cohérents et prévisibles
- **Nested Resources** : Relations hiérarchiques respectées
- **Filtering & Pagination** : Performances optimisées
- **Versioning** : Compatibilité ascendante (v1/, v2/)

#### Sécurité

- **Authentication JWT** : Stateless et scalable
- **CORS Policy** : Configuration stricte des domaines
- **Rate Limiting** : Protection contre les abus (django-ratelimit)
- **Input Validation** : Serializers DRF + sanitization

#### Exemples d'Endpoints Principaux

```
# Authentification
POST /api/auth/login/
POST /api/auth/refresh/
POST /api/auth/logout/

# Évaluations
GET /api/evaluations/
POST /api/evaluations/generate/
GET /api/evaluations/{id}/
POST /api/submissions/

# Apprentissage
GET /api/courses/
GET /api/courses/{id}/modules/
POST /api/quizzes/{id}/submit/
GET /api/progress/

# Recrutement
GET /api/jobs/offers/
POST /api/jobs/applications/
POST /api/jobs/cv-analysis/
```

### 5.3 Performance et Scalabilité

#### Optimisations Frontend

- **Code Splitting** : Lazy loading des composants
- **Memoization** : React.memo et useMemo
- **Virtual Scrolling** : Pour grandes listes
- **Image Optimization** : Formats modernes (WebP)
- **Bundle Analysis** : Monitoring de la taille

#### Optimisations Backend

- **Query Optimization** : select_related et prefetch_related
- **Database Indexing** : Index sur champs critiques
- **Caching** : Redis pour données fréquentes
- **Connection Pooling** : Gestion efficace des connexions DB

#### Monitoring

- **Logging Structuré** : JSON logs avec contexte
- **Métriques Business** : KPIs par module
- **Health Checks** : Monitoring continu
- **Error Tracking** : Sentry pour remontée d'erreurs

---

## 📊 SPÉCIFICATIONS FONCTIONNELLES

### 6.1 Règles Métier Critiques

#### Système de Scoring

- **Pondération questions** : Points selon difficulté
- **Facteur temps** : Bonus rapidité de résolution
- **Pénalités** : Réduction pour réponses incorrectes
- **Seuils validation** : Minimums par type d'évaluation

#### Gestion des Permissions

- **Candidats** : Accès tests assignés + cours publics
- **Organisations** : Gestion évaluations + offres + candidats
- **Administrateurs** : Accès complet avec audit trail
- **Externes** : Accès limité aux tests spécifiques

#### Confidentialité et RGPD

- **Anonymisation** : Données personnelles dans rapports
- **Consentement explicite** : Acceptation utilisation données
- **Rétention limitée** : Suppression automatique après délais
- **Droit à l'oubli** : Suppression sur demande utilisateur

### 6.2 Contraintes Non-Fonctionnelles

#### Performance

- **Temps de réponse** : < 2s pages web, < 500ms API
- **Charge système** : Support 1000+ utilisateurs simultanés
- **Upload fichiers** : Jusqu'à 50MB avec progress
- **Génération rapports** : < 5s pour rapports standards

#### Sécurité

- **Chiffrement** : HTTPS obligatoire, données sensibles chiffrées
- **Audit** : Logs complets des actions critiques
- **Backup** : Sauvegarde automatique quotidienne
- **Recovery** : RTO < 4h, RPO < 1h

#### Disponibilité

- **Uptime** : 99.5% mensuel
- **Maintenance** : Créneaux programmés avec préavis
- **Monitoring** : Surveillance 24/7 avec alertes
- **Scalabilité** : Architecture prête multi-serveurs

---

## 🚀 FEUILLE DE ROUTE

### Phase 1 - MVP (3-4 mois)

- ✅ **Module Évaluation** : CRUD questions, tests, correction automatique
- ✅ **Module Recrutement** : Offres + candidatures basiques
- ✅ **Auth & API** : JWT, documentation, tests unitaires
- ✅ **Frontend** : Interface React + composants principaux

### Phase 2 - Enrichissement (2-3 mois)

- 📚 **Module LMS** : Cours, quiz, certificats, suivi progrès
- 🤖 **IA Basique** : Génération évaluations, analyse CV
- 📊 **Analytics** : Tableaux de bord, métriques détaillées
- 🔍 **Recherche Avancée** : Filtres intelligents, recommandations

### Phase 3 - IA Avancée (3-4 mois)

- 🧠 **IA Générative** : Questions automatiques, contenu personnalisé
- 🔮 **Prédictif** : Scoring candidats, recommandations hyper-ciblées
- 📱 **Mobile** : Applications iOS/Android natives
- 🌍 **Multi-tenant** : Support grands comptes, white-label

---

## 📈 MÉTRIQUES ET KPIs

### Métriques Techniques

- **Performance** : Temps réponse, taux erreur, uptime
- **Qualité** : Couverture tests, bugs production, vélocité dev
- **Sécurité** : Tentatives intrusion, vulnérabilités, audits

### Métriques Business

- **Engagement** : Taux inscription, rétention, temps session
- **Recrutement** : Candidatures/offre, matching, temps embauche
- **Formation** : Taux certification, progression, satisfaction

Ce cahier des charges restructuré présente WIB Challenge de manière concise et organisée, avec des listes claires et des
descriptions courtes, tout en préservant l'exhaustivité fonctionnelle et en ajoutant les spécifications techniques
React + Django REST Framework.
