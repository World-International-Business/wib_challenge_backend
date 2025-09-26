# WIB Challenge - Plateforme d'Évaluation et de Recrutement Technique

WIB Challenge est une plateforme complète dédiée à l'évaluation des compétences techniques et au recrutement. Elle permet aux organisations de gérer efficacement leurs processus de recrutement technique tout en offrant aux candidats une expérience d'évaluation fluide et professionnelle.

## 🎯 Vue d'Ensemble

Cette application web moderne offre un écosystème complet pour :

- **Les organisations** : Publier des offres d'emploi, évaluer les candidats et gérer les processus de recrutement
- **Les candidats** : Passer des évaluations techniques, suivre leur progression et postuler à des offres
- **Les recruteurs** : Gérer les candidatures, évaluer les compétences et prendre des décisions éclairées

## 🚀 Fonctionnalités Principales

### 1. Gestion des Offres d'Emploi

- Publication et gestion des offres d'emploi
- Système de correspondance intelligent entre les offres et les profils candidats
- Gestion des candidatures et du processus de recrutement
- Tableau de bord analytique pour le suivi des performances

### 2. Évaluations Techniques

- Tests de compétences techniques dans divers langages (Python, JavaScript, etc.)
- Questions à choix multiples et exercices pratiques
- Évaluation automatisée des réponses
- Suivi détaillé des performances des candidats

### 3. Gestion des Candidats

- Profils candidats complets avec compétences et expériences
- Historique des évaluations et résultats
- Suivi des candidatures en temps réel
- Système de notation et de commentaires

### 4. API RESTful

- Architecture REST complète avec Django REST Framework
- Authentification JWT sécurisée
- Documentation interactive avec Swagger/OpenAPI
- Intégration avec des services externes

## 🛠️ Technologies Utilisées

### Backend
- **Framework** : Django 5.2.5
- **Base de données** : PostgreSQL / MySQL
- **Cache** : Redis
- **File d'attente** : Celery
- **Authentification** : JWT (JSON Web Tokens)
- **Documentation** : DRF Spectacular (OpenAPI 3)
- **Traitement asynchrone** : Celery

### Services Externes
- Stockage de fichiers : AWS S3 ou équivalent
- Envoi d'emails : SendGrid/Amazon SES
- Évaluation de code : Service d'évaluation personnalisé

## 🚀 Démarrage Rapide

### Prérequis

- Python 3.10+
- PostgreSQL/MySQL
- Redis
- Node.js & npm (pour les assets frontend)

### Installation

1. **Cloner le dépôt**
   ```bash
   git clone [URL_DU_REPO]
   cd wib-challenge/backend-django/wib_challenge_backend
   ```

2. **Créer et activer un environnement virtuel**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Linux/Mac
   # OU
   .\venv\Scripts\activate  # Sur Windows
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer les variables d'environnement**
   Créer un fichier `.env` à la racine du projet avec les variables nécessaires :
   ```env
   DEBUG=True
   SECRET_KEY=votre_cle_secrete
   DATABASE_URL=postgres://user:password@localhost:5432/wib_challenge
   REDIS_URL=redis://localhost:6379/0
   ```

5. **Appliquer les migrations**
   ```bash
   python manage.py migrate
   ```

6. **Créer un superutilisateur**
   ```bash
   python manage.py createsuperuser
   ```

7. **Lancer le serveur de développement**
   ```bash
   python manage.py runserver
   ```

## 📚 Documentation de l'API

La documentation interactive de l'API est disponible à l'adresse :
`http://localhost:8000/api/schema/swagger-ui/`

## 🧪 Tests

Pour exécuter les tests :
```bash
python manage.py test
```

## 🐳 Déploiement avec Docker

Un fichier `Dockerfile` et `docker-compose.yml` sont fournis pour un déploiement conteneurisé :

```bash
docker-compose up --build
```

## 🤝 Contribution

Les contributions sont les bienvenues ! Voici comment contribuer :

1. Forkez le projet
2. Créez votre branche de fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Committez vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Poussez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

## 📝 Licence

Ce projet est sous licence MIT - voir le fichier `LICENSE` pour plus de détails.

## 📞 Contact

Pour toute question ou suggestion, veuillez contacter l'équipe de développement à [email@example.com]

- Base de données riche avec des questions techniques détaillées
- Questions à choix multiples avec explications pédagogiques
- Pondération des questions selon leur complexité
- Classification par technologies et niveaux de difficulté

### 2. Gestion des Candidats et Participants

#### Profils Candidats Complets

- **Informations Personnelles** : Nom, localisation, biographie
- **Parcours Professionnel** : Expériences détaillées avec dates et descriptions
- **Formation Académique** : Diplômes, institutions, spécialisations
- **Compétences Techniques** : Maîtrise de technologies avec niveaux d'expertise
- **Projets Portfolio** : Showcase de réalisations avec images et descriptions
- **Langues** : Compétences linguistiques avec niveaux de maîtrise

#### Types de Participants

- **Utilisateurs Enregistrés** : Professionnels avec comptes complets
- **Candidats Externes** : Participants invités par les organisations
- **Système d'Invitations** : Tokens sécurisés pour accéder aux évaluations

### 3. Plateforme d'Apprentissage (Learning Management System)

#### Structure des Cours

- **Cours Structurés** : Organisation en modules thématiques
- **Contenus Multimédias** : Vidéos, documents PDF, ressources externes
- **Niveaux de Difficulté** : Débutant, Intermédiaire, Avancé
- **Cours Gratuits et Payants** : Modèle économique flexible

#### Système d'Évaluation des Connaissances

- **Quiz Interactifs** : Questions à choix multiples intégrées aux cours
- **Suivi des Progrès** : Pourcentage de completion, statistiques détaillées
- **Certificats** : Validation des acquis à la fin des formations
- **Historique des Résultats** : Conservation des scores et tentatives

#### Engagement et Motivation

- **Système de Progression** : Suivi visuel de l'avancement
- **Statistiques Personnalisées** : Temps d'étude, nombre de quiz réussis
- **Recommandations** : Suggestions de contenus selon le profil

### 4. Portail Emploi et Recrutement

#### Gestion des Offres d'Emploi

- **Publication d'Offres** : Interface complète pour les recruteurs
- **Catégorisation** : Organisation par domaines professionnels
- **Types de Contrats** : CDI, CDD, Stage, Freelance, Télétravail
- **Niveaux d'Expérience** : Adaptation selon l'ancienneté requise

#### Fonctionnalités de Recherche

- **Filtres Avancés** : Localisation, salaire, type de contrat, télétravail
- **Recherche Sémantique** : Algorithmes intelligents de matching
- **Alertes Personnalisées** : Notifications pour les nouveaux postes

#### Processus de Candidature

- **Analyse Automatique de CV** : Intelligence artificielle pour l'évaluation
- **Génération d'Offres Intelligente** : Création automatique basée sur les besoins
- **Suivi des Candidatures** : Dashboard complet pour les recruteurs

### 5. Gestion Organisationnelle

#### Profils d'Entreprises

- **Informations Complètes** : Nom, description, secteur d'activité
- **Localisation** : Adresse, ville, pays
- **Branding** : Logo, site web, présentation visuelle

#### Outils de Recrutement

- **Création d'Évaluations Personnalisées** : Questions spécifiques aux besoins
- **Gestion des Candidats** : Base de données centralisée
- **Invitations Sécurisées** : Système de tokens pour les évaluations
- **Analyses et Rapports** : Statistiques détaillées des performances

#### Correction Automatique

- **Évaluation Instantanée** : Correction automatique des réponses
- **Scores Détaillés** : Points par question, temps de réponse
- **Analyses Comparatives** : Benchmarking avec d'autres candidats

### 6. Système d'Authentification et Sécurité

#### Méthodes de Connexion

- **Authentification Classique** : Email et mot de passe
- **Connexion Google OAuth** : Intégration simplifiée
- **Authentification JWT** : Tokens sécurisés pour l'API
- **Réinitialisation de Mot de Passe** : Processus sécurisé par email

#### Gestion des Rôles

- **Utilisateurs Standards** : Candidats et professionnels
- **Organisations** : Recruteurs et entreprises
- **Administrateurs** : Gestion complète de la plateforme

### 7. Technologies et Domaines Professionnels

#### Classification Intelligente

- **Domaines d'Activité** : Informatique, Marketing, Finance, etc.
- **Technologies Spécialisées** : Python, JavaScript, React, Django, etc.
- **Professions Ciblées** : Développeur Frontend, Data Scientist, etc.

#### Personnalisation des Contenus

- **Questions Adaptées** : Sélection selon la technologie
- **Formations Ciblées** : Cours spécialisés par domaine
- **Évaluations Sur-Mesure** : Tests adaptés aux besoins spécifiques

## 🎪 Fonctionnalités de Compétition

### Challenges Communautaires

- **Compétitions Publiques** : Ouvertes à tous les utilisateurs
- **Périodes Définies** : Dates de début et fin configurables
- **Classements en Temps Réel** : Suivi des performances
- **Récompenses** : Certificats et reconnaissance communautaire

## 📊 Analyses et Rapports

### Tableaux de Bord

- **Statistiques Candidats** : Scores, temps de réponse, comparaisons
- **Métriques Organisations** : Nombre de candidats, taux de réussite
- **Analyses de Performance** : Identification des points forts/faibles

### Exportation de Données

- **Rapports Détaillés** : Analyses complètes des résultats
- **Comparaisons Historiques** : Évolution des performances
- **Métriques Business** : ROI du recrutement, efficacité des formations

## 🔧 Caractéristiques Techniques

### Architecture Robuste

- **API REST** : Interface moderne et scalable
- **Base de Données Optimisée** : SQLite avec possibilité de migration
- **Authentification JWT** : Sécurité moderne et performante
- **Gestion des Médias** : Upload et stockage de fichiers

### Intégrations

- **Services d'Email** : Notifications automatiques
- **Intelligence Artificielle** : Analyse de CV, génération de contenu
- **Caching Intelligent** : Performances optimisées
- **Monitoring** : Logs détaillés et surveillance

## 🎨 Interface Utilisateur

### Expérience Utilisateur Moderne

- **Design Responsive** : Compatible mobile et desktop
- **Navigation Intuitive** : Interface claire et ergonomique
- **Personnalisation** : Adaptation selon les rôles utilisateur

## 🔒 Sécurité et Confidentialité

### Protection des Données

- **Chiffrement des Données** : Sécurisation des informations sensibles
- **Tokens Sécurisés** : Accès contrôlé aux évaluations
- **Audit Trail** : Traçabilité complète des actions
- **Conformité RGPD** : Respect des standards de confidentialité

## 📈 Évolutivité

### Architecture Modulaire

- **Microservices** : Composants indépendants et scalables
- **API Documentée** : Intégrations faciles avec des systèmes tiers
- **Configuration Flexible** : Adaptation aux besoins spécifiques

---

WIB Challenge représente l'avenir du recrutement et de la formation professionnelle, combinant intelligence
artificielle, évaluation précise des compétences et expérience utilisateur optimale pour créer un écosystème complet au
service des talents et des organisations.

## Installation Technique

Après avoir cloné le projet, et créé un environnement virtuel, installer les dépendances avec la commande suivante :

```bash
pip install -r requirements.txt
```

### Configuration

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

