"""Seed automatique des contenus et quiz pour tous les modules existants en base.

Pour chaque module sans contenus, crée :
- 1 lesson markdown (cours théorique)
- 1 lesson vidéo (URL placeholder à remplacer via l'admin)
- 1 lesson ressource externe (URL placeholder)

Pour chaque module sans quiz, crée :
- 1 quiz avec 3-5 questions et 4 choix par question

Usage :
    python manage.py seed_contents          # idempotent (skip si déjà peuplé)
    python manage.py seed_contents --force  # recrée tout
"""
import json
from pathlib import Path

from django.core.management import BaseCommand
from django.db import transaction

from apps.learning.models import Module, Content, Quiz, QuizQuestion, QuizChoice


# ─── Mapping intelligent : titre module → contenus & quiz ───

MODULE_DATA = {
    # ── Cybersécurité Fondamentale ──
    "Bases des Réseaux & Protocoles": {
        "contents": [
            {
                "title": "Introduction aux Réseaux Informatiques",
                "content_type": "markdown",
                "content": "# Introduction aux Réseaux Informatiques\n\n## Qu'est-ce qu'un réseau ?\n\nUn réseau informatique est un ensemble d'équipements interconnectés qui communiquent entre eux pour échanger des données.\n\n### Types de réseaux\n\n- **LAN** (Local Area Network) : réseau local\n- **WAN** (Wide Area Network) : réseau étendu\n- **MAN** (Metropolitan Area Network) : réseau métropolitain\n\n### Composants d'un réseau\n\n- Routeurs\n- Switches\n- Points d'accès\n- Cables et fibres optiques\n\n## Le modèle OSI\n\nLe modèle OSI (Open Systems Interconnection) comporte 7 couches :\n\n1. **Physique** : transmission des bits\n2. **Liaison de données** : gestion des trames\n3. **Réseau** : routage des paquets (IP)\n4. **Transport** : gestion des connexions (TCP/UDP)\n5. **Session** : gestion des sessions\n6. **Présentation** : encodage et chiffrement\n7. **Application** : services réseau (HTTP, FTP, SMTP)\n\n## Le modèle TCP/IP\n\nLe modèle TCP/IP est plus simple avec 4 couches :\n\n1. **Accès réseau** (équivalent OSI 1-2)\n2. **Internet** (équivalent OSI 3)\n3. **Transport** (équivalent OSI 4)\n4. **Application** (équivalent OSI 5-7)",
                "duration_minutes": 30,
            },
            {
                "title": "Vidéo : Les Protocoles Réseau (TCP/IP, HTTP, DNS)",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 45,
            },
            {
                "title": "Ressource : Documentation Officielle CISCO",
                "content_type": "external",
                "resource_url": "https://www.cisco.com/c/fr_fr/index.html",
                "duration_minutes": 20,
            },
        ],
        "quiz": {
            "title": "Quiz : Bases des Réseaux & Protocoles",
            "description": "Testez vos connaissances sur les fondamentaux des réseaux informatiques.",
            "questions": [
                {
                    "title": "Combien de couches comporte le modèle OSI ?",
                    "explanation": "Le modèle OSI comporte 7 couches : Physique, Liaison, Réseau, Transport, Session, Présentation, Application.",
                    "choices": [
                        {"text": "4 couches", "is_correct": False},
                        {"text": "5 couches", "is_correct": False},
                        {"text": "7 couches", "is_correct": True},
                        {"text": "9 couches", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel protocole fonctionne au niveau de la couche Transport ?",
                    "explanation": "TCP et UDP sont les protocoles de la couche Transport (couche 4 du modèle OSI).",
                    "choices": [
                        {"text": "IP", "is_correct": False},
                        {"text": "TCP", "is_correct": True},
                        {"text": "HTTP", "is_correct": False},
                        {"text": "DNS", "is_correct": False},
                    ],
                },
                {
                    "title": "Que signifie LAN ?",
                    "explanation": "LAN signifie Local Area Network, c'est-à-dire un réseau local couvrant une zone géographique limitée.",
                    "choices": [
                        {"text": "Large Area Network", "is_correct": False},
                        {"text": "Local Area Network", "is_correct": True},
                        {"text": "Logical Access Node", "is_correct": False},
                        {"text": "Linked Array Network", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel est le rôle d'un routeur ?",
                    "explanation": "Un routeur achemine les paquets de données entre différents réseaux en choisissant le meilleur chemin.",
                    "choices": [
                        {"text": "Connecter des équipements dans un même réseau local", "is_correct": False},
                        {"text": "Acheminer les paquets entre différents réseaux", "is_correct": True},
                        {"text": "Chiffrer les communications", "is_correct": False},
                        {"text": "Stocker des pages web", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel protocole est utilisé pour résoudre un nom de domaine en adresse IP ?",
                    "explanation": "Le DNS (Domain Name System) traduit les noms de domaine en adresses IP.",
                    "choices": [
                        {"text": "HTTP", "is_correct": False},
                        {"text": "FTP", "is_correct": False},
                        {"text": "DNS", "is_correct": True},
                        {"text": "SMTP", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Introduction à l'Ethical Hacking": {
        "contents": [
            {
                "title": "Fondamentaux de l'Ethical Hacking",
                "content_type": "markdown",
                "content": "# Fondamentaux de l'Ethical Hacking\n\n## Qu'est-ce que l'Ethical Hacking ?\n\nL'ethical hacking consiste à tester la sécurité des systèmes informatiques avec l'autorisation préalable du propriétaire, afin d'identifier et corriger les vulnérabilités.\n\n### Les différents types de hackers\n\n- **White Hat** : hacker éthique, travaille légalement\n- **Black Hat** : hacker malveillant, agit illégalement\n- **Grey Hat** : entre les deux, peut franchir la ligne\n\n### Les phases du hacking éthique\n\n1. **Reconnaissance** : collecte d'informations\n2. **Scanning** : identification des services et ports ouverts\n3. **Gaining Access** : exploitation des vulnérabilités\n4. **Maintaining Access** : maintien de l'accès\n5. **Covering Tracks** : effacement des traces\n\n## Cadre légal\n\nL'ethical hacking doit toujours être pratiqué dans un cadre légal :\n- Contrat d'autorisation signé\n- Périmètre défini\n- Respect de la vie privée\n- Rapport de vulnérabilités",
                "duration_minutes": 35,
            },
            {
                "title": "Vidéo : Introduction au Pentesting",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 40,
            },
            {
                "title": "Ressource : OWASP Top 10",
                "content_type": "external",
                "resource_url": "https://owasp.org/Top10/",
                "duration_minutes": 25,
            },
        ],
        "quiz": {
            "title": "Quiz : Introduction à l'Ethical Hacking",
            "description": "Testez vos connaissances sur les bases du hacking éthique.",
            "questions": [
                {
                    "title": "Qu'est-ce qu'un White Hat Hacker ?",
                    "explanation": "Un White Hat Hacker est un hacker éthique qui teste la sécurité avec autorisation légale.",
                    "choices": [
                        {"text": "Un hacker malveillant", "is_correct": False},
                        {"text": "Un hacker éthique autorisé", "is_correct": True},
                        {"text": "Un hacker anonyme", "is_correct": False},
                        {"text": "Un hacker gouvernemental", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle est la première phase du hacking éthique ?",
                    "explanation": "La reconnaissance (reconnaissance) est la première phase, consistant à collecter des informations sur la cible.",
                    "choices": [
                        {"text": "Exploitation", "is_correct": False},
                        {"text": "Reconnaissance", "is_correct": True},
                        {"text": "Scanning", "is_correct": False},
                        {"text": "Reporting", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce que le OWASP Top 10 ?",
                    "explanation": "Le OWASP Top 10 est une liste des 10 vulnérabilités web les plus critiques.",
                    "choices": [
                        {"text": "Une liste de 10 outils de hacking", "is_correct": False},
                        {"text": "Une liste des 10 vulnérabilités web les plus critiques", "is_correct": True},
                        {"text": "Une liste de 10 hackers célèbres", "is_correct": False},
                        {"text": "Une liste de 10 lois sur la cybersécurité", "is_correct": False},
                    ],
                },
                {
                    "title": "Pourquoi un ethical hacker a-t-il besoin d'une autorisation écrite ?",
                    "explanation": "L'autorisation écrite définit le périmètre légal du test et protège le hacker contre des poursuites.",
                    "choices": [
                        {"text": "Pour des raisons administratives uniquement", "is_correct": False},
                        {"text": "Pour définir le cadre légal et le périmètre du test", "is_correct": True},
                        {"text": "Ce n'est pas nécessaire si on est certifié", "is_correct": False},
                        {"text": "Uniquement pour les tests gouvernementaux", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Bonnes Pratiques en Entreprise": {
        "contents": [
            {
                "title": "Sécurité en Entreprise : Bonnes Pratiques",
                "content_type": "markdown",
                "content": "# Bonnes Pratiques de Sécurité en Entreprise\n\n## Politique de sécurité\n\nUne politique de sécurité définit les règles et procédures pour protéger les actifs informationnels.\n\n### Éléments essentiels\n\n- Gestion des mots de passe\n- Contrôle d'accès\n- Sauvegardes régulières\n- Formation des employés\n- Plan de réponse aux incidents\n\n## Les 3 piliers de la sécurité (CIA Triad)\n\n1. **Confidentialité** : seules les personnes autorisées accèdent aux données\n2. **Intégrité** : les données ne sont pas altérées\n3. **Disponibilité** : les systèmes sont accessibles quand nécessaire\n\n## Mots de passe robustes\n\nUn bon mot de passe :\n- Minimum 12 caractères\n- Mélange majuscules, minuscules, chiffres, caractères spéciaux\n- Unique pour chaque service\n- Changé régulièrement\n- Stocké dans un gestionnaire de mots de passe\n\n## Sensibilisation des employés\n\n- Phishing et ingénierie sociale\n- Ne pas cliquer sur les liens suspects\n- Vérifier l'identité des expéditeurs\n- Signaler les activités suspectes",
                "duration_minutes": 30,
            },
            {
                "title": "Vidéo : Mise en place d'une politique de sécurité",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 35,
            },
            {
                "title": "Ressource : Guide ANSSI",
                "content_type": "external",
                "resource_url": "https://www.ssi.gouv.fr/",
                "duration_minutes": 20,
            },
        ],
        "quiz": {
            "title": "Quiz : Bonnes Pratiques en Entreprise",
            "description": "Testez vos connaissances sur les bonnes pratiques de sécurité en entreprise.",
            "questions": [
                {
                    "title": "Que signifie le triptyque CIA en sécurité ?",
                    "explanation": "CIA = Confidentialité, Intégrité, Disponibilité (Availability en anglais).",
                    "choices": [
                        {"text": "Central Intelligence Agency", "is_correct": False},
                        {"text": "Confidentialité, Intégrité, Disponibilité", "is_correct": True},
                        {"text": "Cyber, Internet, Access", "is_correct": False},
                        {"text": "Control, Identity, Access", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle est la longueur minimale recommandée pour un mot de passe robuste ?",
                    "explanation": "Un mot de passe robuste doit contenir au minimum 12 caractères.",
                    "choices": [
                        {"text": "6 caractères", "is_correct": False},
                        {"text": "8 caractères", "is_correct": False},
                        {"text": "12 caractères", "is_correct": True},
                        {"text": "20 caractères", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce que le phishing ?",
                    "explanation": "Le phishing (hameçonnage) est une technique d'ingénierie sociale pour voler des informations par usurpation d'identité.",
                    "choices": [
                        {"text": "Une attaque par déni de service", "is_correct": False},
                        {"text": "Une technique d'ingénierie sociale", "is_correct": True},
                        {"text": "Un type de virus", "is_correct": False},
                        {"text": "Un pare-feu", "is_correct": False},
                    ],
                },
                {
                    "title": "Que doit faire un employé s'il reçoit un email suspect ?",
                    "explanation": "Il ne doit pas cliquer sur les liens, vérifier l'expéditeur et signaler l'incident.",
                    "choices": [
                        {"text": "Cliquer pour vérifier", "is_correct": False},
                        {"text": "Ignorer et supprimer", "is_correct": False},
                        {"text": "Ne pas cliquer et signaler", "is_correct": True},
                        {"text": "Transférer à tous ses collègues", "is_correct": False},
                    ],
                },
            ],
        },
    },

    # ── Data Science & IA ──
    "Python pour la Data Science": {
        "contents": [
            {
                "title": "Python pour la Data Science : Introduction",
                "content_type": "markdown",
                "content": "# Python pour la Data Science\n\n## Pourquoi Python ?\n\nPython est le langage de référence pour la Data Science grâce à :\n- Sa syntaxe simple et lisible\n- Un écosystème riche de bibliothèques\n- Une communauté active\n\n## Bibliothèques essentielles\n\n### NumPy\n- Calculs numériques performants\n- Manipulation de tableaux multidimensionnels\n- Opérations mathématiques vectorisées\n\n### Pandas\n- Manipulation de données tabulaires (DataFrames)\n- Chargement et export (CSV, Excel, SQL)\n- Nettoyage et transformation de données\n\n### Matplotlib / Seaborn\n- Visualisation de données\n- Graphiques statistiques\n- Personnalisation avancée\n\n## Workflow typique\n\n1. **Collecte** des données\n2. **Nettoyage** et préparation\n3. **Exploration** et analyse\n4. **Visualisation**\n5. **Modélisation**\n6. **Communication** des résultats",
                "duration_minutes": 40,
            },
            {
                "title": "Vidéo : Tutoriel Pandas pour débutants",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 50,
            },
            {
                "title": "Ressource : Documentation officielle Pandas",
                "content_type": "external",
                "resource_url": "https://pandas.pydata.org/docs/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Python pour la Data Science",
            "description": "Testez vos connaissances sur Python et la Data Science.",
            "questions": [
                {
                    "title": "Quelle bibliothèque est utilisée pour les calculs numériques en Python ?",
                    "explanation": "NumPy est la bibliothèque de référence pour les calculs numériques et la manipulation de tableaux.",
                    "choices": [
                        {"text": "Pandas", "is_correct": False},
                        {"text": "NumPy", "is_correct": True},
                        {"text": "Matplotlib", "is_correct": False},
                        {"text": "Django", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle bibliothèque gère les DataFrames ?",
                    "explanation": "Pandas introduit les DataFrames pour manipuler des données tabulaires.",
                    "choices": [
                        {"text": "NumPy", "is_correct": False},
                        {"text": "Pandas", "is_correct": True},
                        {"text": "Seaborn", "is_correct": False},
                        {"text": "Scikit-learn", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle est la première étape d'un projet de Data Science ?",
                    "explanation": "La collecte des données précède le nettoyage, l'exploration et la modélisation.",
                    "choices": [
                        {"text": "Modélisation", "is_correct": False},
                        {"text": "Visualisation", "is_correct": False},
                        {"text": "Collecte des données", "is_correct": True},
                        {"text": "Communication", "is_correct": False},
                    ],
                },
                {
                    "title": "À quoi sert Matplotlib ?",
                    "explanation": "Matplotlib est la bibliothèque de référence pour la visualisation de données en Python.",
                    "choices": [
                        {"text": "Calculs numériques", "is_correct": False},
                        {"text": "Manipulation de DataFrames", "is_correct": False},
                        {"text": "Visualisation de données", "is_correct": True},
                        {"text": "Apprentissage automatique", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Statistiques & Visualisation": {
        "contents": [
            {
                "title": "Statistiques Descriptives et Visualisation",
                "content_type": "markdown",
                "content": "# Statistiques Descriptives et Visualisation\n\n## Statistiques descriptives\n\n### Mesures de tendance centrale\n- **Moyenne** : somme / nombre d'observations\n- **Médiane** : valeur centrale\n- **Mode** : valeur la plus fréquente\n\n### Mesures de dispersion\n- **Variance** : écart moyen au carré\n- **Écart-type** : racine de la variance\n- **Quartiles** : divisent les données en 4 parties\n\n## Visualisation de données\n\n### Types de graphiques\n\n- **Histogramme** : distribution d'une variable\n- **Boxplot** : médiane, quartiles, valeurs aberrantes\n- **Scatter plot** : relation entre deux variables\n- **Line chart** : évolution temporelle\n- **Bar chart** : comparaison de catégories\n- **Heatmap** : matrice de corrélations\n\n## Avec Seaborn\n\n```python\nimport seaborn as sns\nimport matplotlib.pyplot as plt\n\n# Histogramme\nsns.histplot(data=df, x='age')\n\n# Boxplot\nsns.boxplot(data=df, x='groupe', y='valeur')\n\n# Heatmap de corrélation\nsns.heatmap(df.corr(), annot=True)\n\nplt.show()\n```",
                "duration_minutes": 35,
            },
            {
                "title": "Vidéo : Visualisation avec Seaborn",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 45,
            },
            {
                "title": "Ressource : Galerie Seaborn",
                "content_type": "external",
                "resource_url": "https://seaborn.pydata.org/examples/",
                "duration_minutes": 25,
            },
        ],
        "quiz": {
            "title": "Quiz : Statistiques & Visualisation",
            "description": "Testez vos connaissances en statistiques et visualisation.",
            "questions": [
                {
                    "title": "Quelle mesure représente la valeur centrale d'un dataset ?",
                    "explanation": "La médiane est la valeur centrale qui sépare le dataset en deux moitiés.",
                    "choices": [
                        {"text": "La moyenne", "is_correct": False},
                        {"text": "La médiane", "is_correct": True},
                        {"text": "L'écart-type", "is_correct": False},
                        {"text": "La variance", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel graphique montre la distribution d'une variable ?",
                    "explanation": "L'histogramme montre la distribution (fréquence) d'une variable continue.",
                    "choices": [
                        {"text": "Scatter plot", "is_correct": False},
                        {"text": "Histogramme", "is_correct": True},
                        {"text": "Line chart", "is_correct": False},
                        {"text": "Pie chart", "is_correct": False},
                    ],
                },
                {
                    "title": "Que montre un boxplot ?",
                    "explanation": "Le boxplot affiche la médiane, les quartiles et les valeurs aberrantes.",
                    "choices": [
                        {"text": "La moyenne uniquement", "is_correct": False},
                        {"text": "La médiane, quartiles et valeurs aberrantes", "is_correct": True},
                        {"text": "La corrélation entre variables", "is_correct": False},
                        {"text": "L'évolution temporelle", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel graphique visualise une matrice de corrélations ?",
                    "explanation": "La heatmap (carte de chaleur) est idéale pour visualiser une matrice de corrélations.",
                    "choices": [
                        {"text": "Bar chart", "is_correct": False},
                        {"text": "Heatmap", "is_correct": True},
                        {"text": "Scatter plot", "is_correct": False},
                        {"text": "Boxplot", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Machine Learning": {
        "contents": [
            {
                "title": "Introduction au Machine Learning",
                "content_type": "markdown",
                "content": "# Introduction au Machine Learning\n\n## Qu'est-ce que le Machine Learning ?\n\nLe Machine Learning (apprentissage automatique) permet à un système d'apprendre à partir de données pour faire des prédictions sans être explicitement programmé.\n\n## Types d'apprentissage\n\n### 1. Apprentissage supervisé\n- **Classification** : prédire une catégorie (spam/non-spam)\n- **Régression** : prédire une valeur continue (prix)\n- Algorithmes : Linear Regression, Decision Trees, Random Forest, SVM\n\n### 2. Apprentissage non supervisé\n- **Clustering** : regrouper des données similaires\n- **Réduction de dimension** : PCA, t-SNE\n- Algorithmes : K-Means, DBSCAN, Hierarchical Clustering\n\n### 3. Apprentissage par renforcement\n- L'agent apprend par essais et erreurs\n- Récompenses et pénalités\n- Exemple : AlphaGo, voitures autonomes\n\n## Workflow ML\n\n1. Collecte des données\n2. Prétraitement\n3. Séparation train/test\n4. Choix du modèle\n5. Entraînement\n6. Évaluation\n7. Déploiement\n\n## Avec Scikit-learn\n\n```python\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.metrics import accuracy_score\n\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)\nmodel = RandomForestClassifier()\nmodel.fit(X_train, y_train)\npredictions = model.predict(X_test)\nprint(f'Accuracy: {accuracy_score(y_test, predictions)}')\n```",
                "duration_minutes": 50,
            },
            {
                "title": "Vidéo : Tutoriel Scikit-learn",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 60,
            },
            {
                "title": "Ressource : Documentation Scikit-learn",
                "content_type": "external",
                "resource_url": "https://scikit-learn.org/stable/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Machine Learning",
            "description": "Testez vos connaissances sur le Machine Learning.",
            "questions": [
                {
                    "title": "Quels sont les deux types d'apprentissage supervisé ?",
                    "explanation": "L'apprentissage supervisé comprend la classification (catégories) et la régression (valeurs continues).",
                    "choices": [
                        {"text": "Classification et Régression", "is_correct": True},
                        {"text": "Clustering et PCA", "is_correct": False},
                        {"text": "Deep Learning et NLP", "is_correct": False},
                        {"text": "Train et Test", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel algorithme est utilisé pour le clustering ?",
                    "explanation": "K-Means est un algorithme de clustering (apprentissage non supervisé).",
                    "choices": [
                        {"text": "Random Forest", "is_correct": False},
                        {"text": "K-Means", "is_correct": True},
                        {"text": "Linear Regression", "is_correct": False},
                        {"text": "SVM", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle est la première étape du workflow ML ?",
                    "explanation": "La collecte des données est la première étape avant le prétraitement et l'entraînement.",
                    "choices": [
                        {"text": "Entraînement du modèle", "is_correct": False},
                        {"text": "Évaluation", "is_correct": False},
                        {"text": "Collecte des données", "is_correct": True},
                        {"text": "Déploiement", "is_correct": False},
                    ],
                },
                {
                    "title": "À quoi sert train_test_split ?",
                    "explanation": "train_test_split sépare les données en jeu d'entraînement et jeu de test.",
                    "choices": [
                        {"text": "Normaliser les données", "is_correct": False},
                        {"text": "Séparer train et test", "is_correct": True},
                        {"text": "Évaluer le modèle", "is_correct": False},
                        {"text": "Faire des prédictions", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel type d'apprentissage utilise des récompenses ?",
                    "explanation": "L'apprentissage par renforcement utilise un système de récompenses et pénalités.",
                    "choices": [
                        {"text": "Supervisé", "is_correct": False},
                        {"text": "Non supervisé", "is_correct": False},
                        {"text": "Par renforcement", "is_correct": True},
                        {"text": "Semi-supervisé", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Introduction au Deep Learning": {
        "contents": [
            {
                "title": "Fondamentaux du Deep Learning",
                "content_type": "markdown",
                "content": "# Introduction au Deep Learning\n\n## Qu'est-ce que le Deep Learning ?\n\nLe Deep Learning (apprentissage profond) est une branche du Machine Learning utilisant des réseaux de neurones artificiels à multiples couches.\n\n## Réseaux de neurones\n\n### Structure\n- **Couche d'entrée** : reçoit les données\n- **Couches cachées** : traitement (hidden layers)\n- **Couche de sortie** : prédiction\n\n### Neurone artificiel\nUn neurone calcule une somme pondérée de ses entrées, applique une fonction d'activation.\n\n## Frameworks populaires\n\n- **TensorFlow** (Google)\n- **PyTorch** (Meta/Facebook)\n- **Keras** (API haut niveau)\n\n## Applications\n\n- Vision par ordinateur (CNN)\n- Traitement du langage (NLP, Transformers)\n- Reconnaissance vocale\n- Génération d'images (GAN)\n- Voitures autonomes\n\n## Avec TensorFlow/Keras\n\n```python\nimport tensorflow as tf\nfrom tensorflow import keras\n\nmodel = keras.Sequential([\n    keras.layers.Dense(128, activation='relu', input_shape=(784,)),\n    keras.layers.Dropout(0.2),\n    keras.layers.Dense(10, activation='softmax')\n])\n\nmodel.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])\nmodel.fit(X_train, y_train, epochs=10)\n```",
                "duration_minutes": 45,
            },
            {
                "title": "Vidéo : Réseaux de neurones expliqués",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 55,
            },
            {
                "title": "Ressource : Tutoriels TensorFlow",
                "content_type": "external",
                "resource_url": "https://www.tensorflow.org/tutorials",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Introduction au Deep Learning",
            "description": "Testez vos connaissances sur le Deep Learning.",
            "questions": [
                {
                    "title": "Qu'est-ce qu'un réseau de neurones ?",
                    "explanation": "Un réseau de neurones est composé de couches de neurones artificiels interconnectés.",
                    "choices": [
                        {"text": "Un algorithme de tri", "is_correct": False},
                        {"text": "Un réseau de neurones artificiels à multiples couches", "is_correct": True},
                        {"text": "Un type de base de données", "is_correct": False},
                        {"text": "Un protocole réseau", "is_correct": False},
                    ],
                },
                {
                    "title": "Quels sont les frameworks les plus populaires ?",
                    "explanation": "TensorFlow et PyTorch sont les deux frameworks de Deep Learning les plus utilisés.",
                    "choices": [
                        {"text": "Pandas et NumPy", "is_correct": False},
                        {"text": "TensorFlow et PyTorch", "is_correct": True},
                        {"text": "Django et Flask", "is_correct": False},
                        {"text": "Matplotlib et Seaborn", "is_correct": False},
                    ],
                },
                {
                    "title": "Que fait la couche d'entrée d'un réseau ?",
                    "explanation": "La couche d'entrée reçoit les données brutes.",
                    "choices": [
                        {"text": "Elle fait les prédictions finales", "is_correct": False},
                        {"text": "Elle reçoit les données d'entrée", "is_correct": True},
                        {"text": "Elle calcule les gradients", "is_correct": False},
                        {"text": "Elle applique l'activation softmax", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle fonction d'activation est utilisée pour la classification multi-classes ?",
                    "explanation": "Softmax est utilisée en sortie pour la classification multi-classes.",
                    "choices": [
                        {"text": "ReLU", "is_correct": False},
                        {"text": "Sigmoid", "is_correct": False},
                        {"text": "Softmax", "is_correct": True},
                        {"text": "Tanh", "is_correct": False},
                    ],
                },
            ],
        },
    },

    # ── Développement Web Full-Stack ──
    "Fondamentaux HTML, CSS & JavaScript": {
        "contents": [
            {
                "title": "HTML, CSS & JavaScript : Les Bases du Web",
                "content_type": "markdown",
                "content": "# Fondamentaux HTML, CSS & JavaScript\n\n## HTML (Structure)\n\nLe HTML (HyperText Markup Language) définit la structure d'une page web.\n\n```html\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Ma page</title>\n</head>\n<body>\n    <h1>Titre</h1>\n    <p>Paragraphe</p>\n</body>\n</html>\n```\n\n## CSS (Style)\n\nLe CSS (Cascading Style Sheets) gère l'apparence visuelle.\n\n```css\nh1 {\n    color: blue;\n    font-size: 24px;\n}\n\n.container {\n    display: flex;\n    justify-content: center;\n}\n```\n\n## JavaScript (Interactivité)\n\nJavaScript ajoute l'interactivité côté client.\n\n```javascript\nconst button = document.querySelector('button');\nbutton.addEventListener('click', () => {\n    alert('Bouton cliqué !');\n});\n```\n\n## Le DOM\n\nLe DOM (Document Object Model) représente la page web comme une arbre d'objets que JavaScript peut manipuler.",
                "duration_minutes": 40,
            },
            {
                "title": "Vidéo : HTML CSS JavaScript pour débutants",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 60,
            },
            {
                "title": "Ressource : MDN Web Docs",
                "content_type": "external",
                "resource_url": "https://developer.mozilla.org/fr/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Fondamentaux HTML, CSS & JavaScript",
            "description": "Testez vos connaissances sur les bases du développement web.",
            "questions": [
                {
                    "title": "À quoi sert le HTML ?",
                    "explanation": "Le HTML définit la structure et le contenu d'une page web.",
                    "choices": [
                        {"text": "Styliser la page", "is_correct": False},
                        {"text": "Structurer le contenu", "is_correct": True},
                        {"text": "Ajouter de l'interactivité", "is_correct": False},
                        {"text": "Gérer la base de données", "is_correct": False},
                    ],
                },
                {
                    "title": "Que signifie CSS ?",
                    "explanation": "CSS signifie Cascading Style Sheets (feuilles de style en cascade).",
                    "choices": [
                        {"text": "Computer Style System", "is_correct": False},
                        {"text": "Cascading Style Sheets", "is_correct": True},
                        {"text": "Creative Style Solution", "is_correct": False},
                        {"text": "Client Side Script", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce que le DOM ?",
                    "explanation": "Le DOM (Document Object Model) représente la page comme un arbre d'objets manipulable par JavaScript.",
                    "choices": [
                        {"text": "Un protocole réseau", "is_correct": False},
                        {"text": "Document Object Model", "is_correct": True},
                        {"text": "Data Object Model", "is_correct": False},
                        {"text": "Display Output Module", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle méthode ajoute un écouteur d'événement en JavaScript ?",
                    "explanation": "addEventListener() attache une fonction à un événement.",
                    "choices": [
                        {"text": "attachEvent()", "is_correct": False},
                        {"text": "addEventListener()", "is_correct": True},
                        {"text": "onEvent()", "is_correct": False},
                        {"text": "listen()", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Frameworks Front-end (React)": {
        "contents": [
            {
                "title": "React : Framework Front-end Moderne",
                "content_type": "markdown",
                "content": "# React : Framework Front-end\n\n## Qu'est-ce que React ?\n\nReact est une bibliothèque JavaScript développée par Meta pour construire des interfaces utilisateur.\n\n## Concepts clés\n\n### Composants\nLes composants sont des blocs réutilisables d'interface.\n\n```jsx\nfunction Welcome(props) {\n    return <h1>Bonjour, {props.name}</h1>;\n}\n```\n\n### JSX\nJSX permet d'écrire du HTML dans JavaScript.\n\n### State et Props\n- **State** : état interne du composant\n- **Props** : données passées au composant\n\n### Hooks\n\n```jsx\nimport { useState, useEffect } from 'react';\n\nfunction Counter() {\n    const [count, setCount] = useState(0);\n    return <button onClick={() => setCount(count + 1)}>{count}</button>;\n}\n```\n\n## Cycle de vie\n\n1. Mounting (montage)\n2. Updating (mise à jour)\n3. Unmounting (démontage)",
                "duration_minutes": 45,
            },
            {
                "title": "Vidéo : Tutoriel React pour débutants",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 70,
            },
            {
                "title": "Ressource : Documentation officielle React",
                "content_type": "external",
                "resource_url": "https://react.dev/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Frameworks Front-end (React)",
            "description": "Testez vos connaissances sur React.",
            "questions": [
                {
                    "title": "Qu'est-ce qu'un composant React ?",
                    "explanation": "Un composant est un bloc réutilisable d'interface utilisateur.",
                    "choices": [
                        {"text": "Un fichier CSS", "is_correct": False},
                        {"text": "Un bloc réutilisable d'UI", "is_correct": True},
                        {"text": "Une fonction serveur", "is_correct": False},
                        {"text": "Un type de base de données", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce que JSX ?",
                    "explanation": "JSX est une extension syntaxique permettant d'écrire du HTML dans JavaScript.",
                    "choices": [
                        {"text": "Un nouveau langage de programmation", "is_correct": False},
                        {"text": "Du HTML dans JavaScript", "is_correct": True},
                        {"text": "Un framework CSS", "is_correct": False},
                        {"text": "Un protocole réseau", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle hook gère l'état local ?",
                    "explanation": "useState gère l'état local d'un composant.",
                    "choices": [
                        {"text": "useEffect", "is_correct": False},
                        {"text": "useState", "is_correct": True},
                        {"text": "useContext", "is_correct": False},
                        {"text": "useMemo", "is_correct": False},
                    ],
                },
                {
                    "title": "Que sont les Props ?",
                    "explanation": "Les Props sont les données passées d'un composant parent à un enfant.",
                    "choices": [
                        {"text": "L'état interne du composant", "is_correct": False},
                        {"text": "Les données passées au composant", "is_correct": True},
                        {"text": "Des hooks personnalisés", "is_correct": False},
                        {"text": "Des événements", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Back-end avec Node.js & Express": {
        "contents": [
            {
                "title": "Node.js & Express : Back-end JavaScript",
                "content_type": "markdown",
                "content": "# Back-end avec Node.js & Express\n\n## Node.js\n\nNode.js permet d'exécuter JavaScript côté serveur.\n\n### Caractéristiques\n- Runtime JavaScript basé sur V8\n- Asynchrone et événementiel\n- Idéal pour les API et microservices\n\n## Express.js\n\nExpress est un framework minimaliste pour Node.js.\n\n```javascript\nconst express = require('express');\nconst app = express();\n\napp.use(express.json());\n\napp.get('/api/users', (req, res) => {\n    res.json({ users: [] });\n});\n\napp.post('/api/users', (req, res) => {\n    const user = req.body;\n    res.status(201).json(user);\n});\n\napp.listen(3000, () => console.log('Server running on port 3000'));\n```\n\n## Middleware\n\nLes middlewares interceptent les requêtes :\n- Parsing JSON\n- Authentification\n- Logging\n- Gestion d'erreurs\n\n## REST API\n\nMéthodes HTTP :\n- GET : lire\n- POST : créer\n- PUT/PATCH : mettre à jour\n- DELETE : supprimer",
                "duration_minutes": 50,
            },
            {
                "title": "Vidéo : Créer une API REST avec Express",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 65,
            },
            {
                "title": "Ressource : Documentation Express.js",
                "content_type": "external",
                "resource_url": "https://expressjs.com/",
                "duration_minutes": 25,
            },
        ],
        "quiz": {
            "title": "Quiz : Back-end avec Node.js & Express",
            "description": "Testez vos connaissances sur Node.js et Express.",
            "questions": [
                {
                    "title": "Qu'est-ce que Node.js ?",
                    "explanation": "Node.js est un runtime JavaScript basé sur le moteur V8 de Chrome, pour exécuter JS côté serveur.",
                    "choices": [
                        {"text": "Un framework CSS", "is_correct": False},
                        {"text": "Un runtime JavaScript côté serveur", "is_correct": True},
                        {"text": "Une base de données", "is_correct": False},
                        {"text": "Un navigateur web", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle méthode HTTP crée une ressource ?",
                    "explanation": "POST est utilisé pour créer une nouvelle ressource.",
                    "choices": [
                        {"text": "GET", "is_correct": False},
                        {"text": "POST", "is_correct": True},
                        {"text": "DELETE", "is_correct": False},
                        {"text": "HEAD", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce qu'un middleware Express ?",
                    "explanation": "Un middleware est une fonction qui intercepte les requêtes/réponses.",
                    "choices": [
                        {"text": "Un composant React", "is_correct": False},
                        {"text": "Une fonction qui intercepte les requêtes", "is_correct": True},
                        {"text": "Un type de base de données", "is_correct": False},
                        {"text": "Un protocole réseau", "is_correct": False},
                    ],
                },
                {
                    "title": "Sur quel moteur JavaScript repose Node.js ?",
                    "explanation": "Node.js utilise le moteur V8 de Google Chrome.",
                    "choices": [
                        {"text": "SpiderMonkey", "is_correct": False},
                        {"text": "V8", "is_correct": True},
                        {"text": "JavaScriptCore", "is_correct": False},
                        {"text": "Chakra", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Bases de données & Déploiement": {
        "contents": [
            {
                "title": "Bases de Données et Déploiement Web",
                "content_type": "markdown",
                "content": "# Bases de Données & Déploiement\n\n## Types de bases de données\n\n### SQL (relationnelles)\n- PostgreSQL, MySQL, SQLite\n- Tables avec schéma fixe\n- Transactions ACID\n- Jointures\n\n### NoSQL\n- MongoDB (document)\n- Redis (clé-valeur)\n- Cassandra (colonne)\n- Neo4j (graphe)\n\n## ORMs\n\n### Prisma (Node.js)\n```javascript\nconst user = await prisma.user.create({\n    data: { email: 'alice@example.com' }\n});\n```\n\n### Sequelize (Node.js)\n```javascript\nconst User = sequelize.define('User', { email: DataTypes.STRING });\n```\n\n## Déploiement\n\n### Plateformes\n- Vercel (frontend + serverless)\n- Railway / Render (backend)\n- Docker / Kubernetes\n- AWS / GCP / Azure\n\n### CI/CD\n- GitHub Actions\n- Tests automatisés\n- Déploiement automatique\n\n## Variables d'environnement\n- DATABASE_URL\n- JWT_SECRET\n- API_KEY\n- PORT",
                "duration_minutes": 45,
            },
            {
                "title": "Vidéo : Déployer une application full-stack",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 55,
            },
            {
                "title": "Ressource : Guide Docker",
                "content_type": "external",
                "resource_url": "https://docs.docker.com/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Bases de données & Déploiement",
            "description": "Testez vos connaissances sur les bases de données et le déploiement.",
            "questions": [
                {
                    "title": "Quelle base de données est de type document ?",
                    "explanation": "MongoDB est une base de données NoSQL de type document (JSON/BSON).",
                    "choices": [
                        {"text": "PostgreSQL", "is_correct": False},
                        {"text": "MongoDB", "is_correct": True},
                        {"text": "Redis", "is_correct": False},
                        {"text": "MySQL", "is_correct": False},
                    ],
                },
                {
                    "title": "Que signifie ACID ?",
                    "explanation": "ACID = Atomicité, Cohérence, Isolation, Durabilité (propriétés des transactions SQL).",
                    "choices": [
                        {"text": "Atomicité, Cohérence, Isolation, Durabilité", "is_correct": True},
                        {"text": "Access, Control, Identity, Data", "is_correct": False},
                        {"text": "Advanced Computing In Database", "is_correct": False},
                        {"text": "Automated Cloud Integration Data", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce que CI/CD ?",
                    "explanation": "CI/CD = Continuous Integration / Continuous Deployment (intégration et déploiement continus).",
                    "choices": [
                        {"text": "Client Interface / Client Data", "is_correct": False},
                        {"text": "Continuous Integration / Continuous Deployment", "is_correct": True},
                        {"text": "Centralized Integration / Centralized Data", "is_correct": False},
                        {"text": "Code Inspection / Code Debugging", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel outil gère le déploiement en conteneurs ?",
                    "explanation": "Docker permet de conteneuriser et déployer des applications.",
                    "choices": [
                        {"text": "Docker", "is_correct": True},
                        {"text": "React", "is_correct": False},
                        {"text": "Express", "is_correct": False},
                        {"text": "MongoDB", "is_correct": False},
                    ],
                },
            ],
        },
    },

    # ── DevOps & Cloud Computing ──
    "Linux & Ligne de Commande": {
        "contents": [
            {
                "title": "Linux et Ligne de Commande",
                "content_type": "markdown",
                "content": "# Linux & Ligne de Commande\n\n## Pourquoi Linux ?\n\nLinux est le système d'exploitation dominant sur les serveurs.\n\n## Commandes essentielles\n\n```bash\n# Navigation\npwd              # répertoire courant\ncd /home/user    # changer de répertoire\nls -la           # lister les fichiers\n\n# Manipulation de fichiers\nmkdir dossier    # créer un dossier\ntouch fichier.txt # créer un fichier\ncp src dest      # copier\nmv src dest      # déplacer/renommer\nrm fichier       # supprimer\nrm -rf dossier   # supprimer un dossier\n\n# Recherche et texte\ngrep \"motif\" fichier\nfind /path -name \"*.py\"\ncat fichier\nless fichier\nhead -n 10 fichier\ntail -n 10 fichier\n\n# Permissions\nchmod 755 fichier\nchown user:group fichier\n\n# Processus\nps aux\ntop\nkill PID\n\n# Réseau\nping google.com\ncurl http://example.com\nnetstat -tulpn\n```\n\n## Éditeurs en ligne de commande\n- **nano** : simple, débutant\n- **vim** : puissant, courbe d'apprentissage\n- **emacs** : extensible",
                "duration_minutes": 40,
            },
            {
                "title": "Vidéo : Linux pour débutants",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 50,
            },
            {
                "title": "Ressource : Tutoriel Linux",
                "content_type": "external",
                "resource_url": "https://linuxjourney.com/",
                "duration_minutes": 25,
            },
        ],
        "quiz": {
            "title": "Quiz : Linux & Ligne de Commande",
            "description": "Testez vos connaissances sur Linux.",
            "questions": [
                {
                    "title": "Que fait la commande 'pwd' ?",
                    "explanation": "pwd (print working directory) affiche le répertoire courant.",
                    "choices": [
                        {"text": "Affiche le répertoire courant", "is_correct": True},
                        {"text": "Liste les fichiers", "is_correct": False},
                        {"text": "Change de répertoire", "is_correct": False},
                        {"text": "Crée un dossier", "is_correct": False},
                    ],
                },
                {
                    "title": "Que fait 'chmod 755' ?",
                    "explanation": "chmod 755 donne rwx au propriétaire et r-x au groupe et aux autres.",
                    "choices": [
                        {"text": "Supprime un fichier", "is_correct": False},
                        {"text": "Modifie les permissions", "is_correct": True},
                        {"text": "Change le propriétaire", "is_correct": False},
                        {"text": "Compile un programme", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle commande affiche les processus en cours ?",
                    "explanation": "ps aux ou top affichent les processus actifs.",
                    "choices": [
                        {"text": "ls", "is_correct": False},
                        {"text": "ps aux", "is_correct": True},
                        {"text": "cd", "is_correct": False},
                        {"text": "mkdir", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle commande cherche un motif dans un fichier ?",
                    "explanation": "grep recherche un motif (pattern) dans un fichier.",
                    "choices": [
                        {"text": "find", "is_correct": False},
                        {"text": "grep", "is_correct": True},
                        {"text": "cat", "is_correct": False},
                        {"text": "touch", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Docker & Conteneurisation": {
        "contents": [
            {
                "title": "Docker : Conteneurisation d'Applications",
                "content_type": "markdown",
                "content": "# Docker & Conteneurisation\n\n## Qu'est-ce que Docker ?\n\nDocker permet d'empaqueter une application et ses dépendances dans un conteneur portable.\n\n## Concepts clés\n\n- **Image** : modèle immuable (snapshot)\n- **Conteneur** : instance d'image en cours d'exécution\n- **Dockerfile** : script de construction d'image\n- **Docker Hub** : registre d'images\n- **Volume** : persistance des données\n\n## Dockerfile\n\n```dockerfile\nFROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY . .\nCMD [\"python\", \"manage.py\", \"runserver\", \"0.0.0.0:8000\"]\n```\n\n## Commandes essentielles\n\n```bash\ndocker build -t monapp .          # construire une image\ndocker run -p 8000:8000 monapp     # lancer un conteneur\ndocker ps                          # conteneurs actifs\ndocker stop <id>                   # arrêter\ndocker rm <id>                     # supprimer\ndocker images                      # lister les images\ndocker-compose up -d               # lancer avec compose\n```\n\n## Docker Compose\n\n```yaml\nversion: '3.8'\nservices:\n  web:\n    build: .\n    ports:\n      - '8000:8000'\n  db:\n    image: postgres:15\n    environment:\n      POSTGRES_DB: app\n```",
                "duration_minutes": 45,
            },
            {
                "title": "Vidéo : Docker pour débutants",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 55,
            },
            {
                "title": "Ressource : Documentation Docker",
                "content_type": "external",
                "resource_url": "https://docs.docker.com/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Docker & Conteneurisation",
            "description": "Testez vos connaissances sur Docker.",
            "questions": [
                {
                    "title": "Quelle est la différence entre image et conteneur ?",
                    "explanation": "L'image est immuable (modèle), le conteneur est une instance en cours d'exécution.",
                    "choices": [
                        {"text": "C'est la même chose", "is_correct": False},
                        {"text": "L'image est le modèle, le conteneur est l'instance", "is_correct": True},
                        {"text": "Le conteneur est le modèle, l'image est l'instance", "is_correct": False},
                        {"text": "Aucune relation", "is_correct": False},
                    ],
                },
                {
                    "title": "Que contient un Dockerfile ?",
                    "explanation": "Un Dockerfile contient les instructions pour construire une image Docker.",
                    "choices": [
                        {"text": "Le code source de l'application", "is_correct": False},
                        {"text": "Les instructions de construction d'image", "is_correct": True},
                        {"text": "La configuration réseau", "is_correct": False},
                        {"text": "Les mots de passe", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle commande construit une image Docker ?",
                    "explanation": "docker build construit une image à partir d'un Dockerfile.",
                    "choices": [
                        {"text": "docker run", "is_correct": False},
                        {"text": "docker build", "is_correct": True},
                        {"text": "docker start", "is_correct": False},
                        {"text": "docker create", "is_correct": False},
                    ],
                },
                {
                    "title": "À quoi sert Docker Compose ?",
                    "explanation": "Docker Compose permet de définir et lancer plusieurs conteneurs ensemble.",
                    "choices": [
                        {"text": "Construire des images", "is_correct": False},
                        {"text": "Orchestrer plusieurs conteneurs", "is_correct": True},
                        {"text": "Gérer le réseau", "is_correct": False},
                        {"text": "Compiler du code", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Création et gestion de conteneurs applicatifs.": {
        "contents": [
            {
                "title": "Gestion Avancée des Conteneurs",
                "content_type": "markdown",
                "content": "# Création et Gestion de Conteneurs Applicatifs\n\n## Bonnes pratiques\n\n### Images légères\n- Utiliser des images de base minimales (alpine, slim)\n- Multi-stage builds\n- .dockerignore\n\n### Multi-stage build\n```dockerfile\nFROM node:18 AS builder\nWORKDIR /app\nCOPY . .\nRUN npm ci && npm run build\n\nFROM nginx:alpine\nCOPY --from=builder /app/dist /usr/share/nginx/html\n```\n\n## Sécurité\n- Ne pas exécuter en root\n- Scanner les images (Trivy, Snyk)\n- Variables d'environnement sensibles via secrets\n\n## Orchestration\n- **Docker Swarm** : orchestration native\n- **Kubernetes** : standard de l'industrie\n- **Nomad** : alternative simple\n\n## Monitoring\n- Prometheus + Grafana\n- cAdvisor\n- Logs centralisés (ELK)",
                "duration_minutes": 40,
            },
            {
                "title": "Vidéo : Orchestration de conteneurs",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 50,
            },
            {
                "title": "Ressource : Kubernetes Documentation",
                "content_type": "external",
                "resource_url": "https://kubernetes.io/fr/docs/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Gestion de Conteneurs",
            "description": "Testez vos connaissances sur la gestion de conteneurs.",
            "questions": [
                {
                    "title": "Quel est l'avantage d'un multi-stage build ?",
                    "explanation": "Le multi-stage build permet de réduire la taille de l'image finale en ne gardant que les artefacts nécessaires.",
                    "choices": [
                        {"text": "Accélérer le build", "is_correct": False},
                        {"text": "Réduire la taille de l'image finale", "is_correct": True},
                        {"text": "Compiler plus vite", "is_correct": False},
                        {"text": "Ajouter plus de dépendances", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel outil est le standard d'orchestration ?",
                    "explanation": "Kubernetes est le standard de l'industrie pour l'orchestration de conteneurs.",
                    "choices": [
                        {"text": "Docker Compose", "is_correct": False},
                        {"text": "Kubernetes", "is_correct": True},
                        {"text": "Vagrant", "is_correct": False},
                        {"text": "Ansible", "is_correct": False},
                    ],
                },
                {
                    "title": "Pourquoi ne pas exécuter un conteneur en root ?",
                    "explanation": "Par sécurité, exécuter en root augmente les risques en cas de compromission.",
                    "choices": [
                        {"text": "Pour des raisons de performance", "is_correct": False},
                        {"text": "Pour des raisons de sécurité", "is_correct": True},
                        {"text": "Pour économiser de la mémoire", "is_correct": False},
                        {"text": "Pour accélérer le démarrage", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel outil scanne les vulnérabilités d'images ?",
                    "explanation": "Trivy est un outil populaire pour scanner les vulnérabilités d'images Docker.",
                    "choices": [
                        {"text": "Trivy", "is_correct": True},
                        {"text": "Grafana", "is_correct": False},
                        {"text": "Prometheus", "is_correct": False},
                        {"text": "cAdvisor", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Cloud Computing (AWS/Azure)": {
        "contents": [
            {
                "title": "Cloud Computing : AWS et Azure",
                "content_type": "markdown",
                "content": "# Cloud Computing (AWS / Azure)\n\n## Modèles de service\n\n- **IaaS** : Infrastructure as a Service (EC2, VMs)\n- **PaaS** : Platform as a Service (App Service, Elastic Beanstalk)\n- **SaaS** : Software as a Service (Office 365, Gmail)\n\n## AWS\n\n### Services clés\n- **EC2** : machines virtuelles\n- **S3** : stockage d'objets\n- **RDS** : bases de données managées\n- **Lambda** : serverless\n- **VPC** : réseau privé virtuel\n- **IAM** : gestion des identités\n\n## Azure\n\n### Services clés\n- **Virtual Machines** : machines virtuelles\n- **Blob Storage** : stockage\n- **Azure SQL** : base de données\n- **Functions** : serverless\n- **AKS** : Kubernetes managé\n\n## Bonnes pratiques\n- Choisir la bonne région\n- Sécuriser avec IAM\n- Monitorer les coûts\n- Sauvegardes automatiques\n- Multi-AZ pour la haute disponibilité",
                "duration_minutes": 50,
            },
            {
                "title": "Vidéo : Introduction au Cloud AWS",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 60,
            },
            {
                "title": "Ressource : Documentation AWS",
                "content_type": "external",
                "resource_url": "https://docs.aws.amazon.com/",
                "duration_minutes": 30,
            },
        ],
        "quiz": {
            "title": "Quiz : Cloud Computing (AWS/Azure)",
            "description": "Testez vos connaissances sur le Cloud.",
            "questions": [
                {
                    "title": "Que signifie IaaS ?",
                    "explanation": "IaaS = Infrastructure as a Service (infrastructure en tant que service).",
                    "choices": [
                        {"text": "Internet as a Service", "is_correct": False},
                        {"text": "Infrastructure as a Service", "is_correct": True},
                        {"text": "Integration as a Service", "is_correct": False},
                        {"text": "Identity as a Service", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel service AWS gère le stockage d'objets ?",
                    "explanation": "S3 (Simple Storage Service) est le service de stockage d'objets d'AWS.",
                    "choices": [
                        {"text": "EC2", "is_correct": False},
                        {"text": "S3", "is_correct": True},
                        {"text": "RDS", "is_correct": False},
                        {"text": "Lambda", "is_correct": False},
                    ],
                },
                {
                    "title": "Que permet AWS Lambda ?",
                    "explanation": "Lambda est un service serverless : on exécute du code sans gérer de serveurs.",
                    "choices": [
                        {"text": "Stocker des fichiers", "is_correct": False},
                        {"text": "Exécuter du code serverless", "is_correct": True},
                        {"text": "Gérer une base de données", "is_correct": False},
                        {"text": "Créer des VMs", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel service Azure équivaut à EC2 ?",
                    "explanation": "Azure Virtual Machines équivaut à AWS EC2.",
                    "choices": [
                        {"text": "Azure Functions", "is_correct": False},
                        {"text": "Azure Virtual Machines", "is_correct": True},
                        {"text": "Azure Blob Storage", "is_correct": False},
                        {"text": "Azure SQL", "is_correct": False},
                    ],
                },
            ],
        },
    },

    # ── Gestion de Projet Agile & Scrum ──
    "Comprendre et appliquer les méthodologies agiles en entreprise : principes Scrum, rôles clés, outils de gestion de projet et simulation de sprint.": {
        "contents": [
            {
                "title": "Introduction à Agile et Scrum",
                "content_type": "markdown",
                "content": "# Introduction à Agile et Scrum\n\n## Le manifeste Agile\n\n- **Individus et interactions** plutôt que processus et outils\n- **Logiciel fonctionnel** plutôt que documentation exhaustive\n- **Collaboration client** plutôt que négociation de contrat\n- **Réagir au changement** plutôt que suivre un plan\n\n## Scrum\n\nScrum est un framework agile pour gérer des projets complexes.\n\n### Rôles\n- **Product Owner** : vision produit, priorité du backlog\n- **Scrum Master** : facilite, retire les obstacles\n- **Équipe de développement** : construit le produit\n\n### Cérémonies\n- **Sprint Planning** : planification du sprint\n- **Daily Scrum** : point quotidien (15 min)\n- **Sprint Review** : démonstration\n- **Sprint Retrospective** : amélioration continue\n\n### Artefacts\n- **Product Backlog** : liste des fonctionnalités\n- **Sprint Backlog** : tâches du sprint\n- **Increment** : produit fonctionnel\n\n## Le Sprint\n\nUn sprint dure généralement 2 à 4 semaines.",
                "duration_minutes": 40,
            },
            {
                "title": "Vidéo : Scrum en pratique",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 45,
            },
            {
                "title": "Ressource : Guide Scrum officiel",
                "content_type": "external",
                "resource_url": "https://scrumguides.org/scrum-guide.html",
                "duration_minutes": 25,
            },
        ],
        "quiz": {
            "title": "Quiz : Introduction à Agile et Scrum",
            "description": "Testez vos connaissances sur Agile et Scrum.",
            "questions": [
                {
                    "title": "Qui est responsable du Product Backlog ?",
                    "explanation": "Le Product Owner gère et priorise le Product Backlog.",
                    "choices": [
                        {"text": "Le Scrum Master", "is_correct": False},
                        {"text": "Le Product Owner", "is_correct": True},
                        {"text": "L'équipe de développement", "is_correct": False},
                        {"text": "Le chef de projet", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle est la durée typique d'un sprint ?",
                    "explanation": "Un sprint dure généralement 2 à 4 semaines.",
                    "choices": [
                        {"text": "1 jour", "is_correct": False},
                        {"text": "2 à 4 semaines", "is_correct": True},
                        {"text": "3 mois", "is_correct": False},
                        {"text": "6 mois", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce que le Daily Scrum ?",
                    "explanation": "Le Daily Scrum est un point quotidien de 15 minutes pour synchroniser l'équipe.",
                    "choices": [
                        {"text": "Une réunion mensuelle", "is_correct": False},
                        {"text": "Un point quotidien de 15 minutes", "is_correct": True},
                        {"text": "Une démonstration client", "is_correct": False},
                        {"text": "Une rétrospective", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel est le rôle du Scrum Master ?",
                    "explanation": "Le Scrum Master facilite le processus et retire les obstacles.",
                    "choices": [
                        {"text": "Définir la vision produit", "is_correct": False},
                        {"text": "Faciliter le processus Scrum", "is_correct": True},
                        {"text": "Écrire le code", "is_correct": False},
                        {"text": "Gérer le budget", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Le Framework Scrum": {
        "contents": [
            {
                "title": "Le Framework Scrum en Détail",
                "content_type": "markdown",
                "content": "# Le Framework Scrum\n\n## Valeurs Scrum\n\n1. **Engagement** : s'engager à atteindre les objectifs\n2. **Focus** : se concentrer sur le travail du sprint\n3. **Ouverture** : transparence sur le travail\n4. **Respect** : respecter les autres\n5. **Courage** : oser dire non\n\n## Événements Scrum\n\n### Sprint\nConteneur de tous les autres événements, 2-4 semaines.\n\n### Sprint Planning\n- Objectif du sprint\n- Sélection des items du backlog\n- Planification du travail\n\n### Daily Scrum\n- 15 minutes chaque jour\n- 3 questions : qu'ai-je fait, que vais-je faire, obstacles ?\n\n### Sprint Review\n- Démonstration du produit\n- Feedback des stakeholders\n- Adaptation du backlog\n\n### Sprint Retrospective\n- Ce qui a bien fonctionné\n- Ce qui peut être amélioré\n- Plan d'action\n\n## Definition of Done (DoD)\n\nCritères de qualité partagés : code testé, revu, documenté, déployable.",
                "duration_minutes": 45,
            },
            {
                "title": "Vidéo : Les événements Scrum",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 50,
            },
            {
                "title": "Ressource : Scrum.org",
                "content_type": "external",
                "resource_url": "https://www.scrum.org/",
                "duration_minutes": 20,
            },
        ],
        "quiz": {
            "title": "Quiz : Le Framework Scrum",
            "description": "Testez vos connaissances sur le framework Scrum.",
            "questions": [
                {
                    "title": "Combien de valeurs Scrum existe-t-il ?",
                    "explanation": "Il existe 5 valeurs Scrum : Engagement, Focus, Ouverture, Respect, Courage.",
                    "choices": [
                        {"text": "3", "is_correct": False},
                        {"text": "5", "is_correct": True},
                        {"text": "7", "is_correct": False},
                        {"text": "12", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce que la Definition of Done ?",
                    "explanation": "La DoD définit les critères partagés pour considérer un item comme terminé.",
                    "choices": [
                        {"text": "Une liste de bugs", "is_correct": False},
                        {"text": "Les critères de qualité partagés", "is_correct": True},
                        {"text": "Le backlog produit", "is_correct": False},
                        {"text": "Le planning du sprint", "is_correct": False},
                    ],
                },
                {
                    "title": "Que se passe-t-il lors de la Sprint Review ?",
                    "explanation": "On y présente l'incrément produit et on recueille le feedback des stakeholders.",
                    "choices": [
                        {"text": "On planifie le prochain sprint", "is_correct": False},
                        {"text": "On présente l'incrément et on recueille le feedback", "is_correct": True},
                        {"text": "On corrige les bugs", "is_correct": False},
                        {"text": "On écrit le backlog", "is_correct": False},
                    ],
                },
                {
                    "title": "Que se passe-t-il lors de la rétrospective ?",
                    "explanation": "La rétrospective vise à améliorer le processus de travail de l'équipe.",
                    "choices": [
                        {"text": "Démontrer le produit au client", "is_correct": False},
                        {"text": "Améliorer le processus de travail", "is_correct": True},
                        {"text": "Planifier le sprint", "is_correct": False},
                        {"text": "Écrire du code", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Outils de Gestion de Projet": {
        "contents": [
            {
                "title": "Outils de Gestion de Projet Agile",
                "content_type": "markdown",
                "content": "# Outils de Gestion de Projet\n\n## Outils populaires\n\n### Jira\n- Outil de référence pour Scrum\n- Backlog, sprints, boards\n- Reporting et suivi\n\n### Trello\n- Kanban boards\n- Simple et visuel\n- Idéal pour petits projets\n\n### Asana\n- Gestion de tâches\n- Timeline et calendrier\n- Collaboration\n\n### Notion\n- Tout-en-un\n- Documentation + gestion\n- Templates\n\n### GitHub Projects\n- Intégration code\n- Automation\n- Issues et PRs\n\n## Critères de choix\n\n- Taille de l'équipe\n- Budget\n- Complexité du projet\n- Intégrations nécessaires\n- Préférence Kanban vs Scrum",
                "duration_minutes": 30,
            },
            {
                "title": "Vidéo : Comparatif des outils de gestion de projet",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 35,
            },
            {
                "title": "Ressource : Atlassian Jira Guide",
                "content_type": "external",
                "resource_url": "https://www.atlassian.com/agile/tutorials",
                "duration_minutes": 20,
            },
        ],
        "quiz": {
            "title": "Quiz : Outils de Gestion de Projet",
            "description": "Testez vos connaissances sur les outils de gestion de projet.",
            "questions": [
                {
                    "title": "Quel outil est le plus utilisé pour Scrum ?",
                    "explanation": "Jira (Atlassian) est l'outil de référence pour Scrum.",
                    "choices": [
                        {"text": "Jira", "is_correct": True},
                        {"text": "Excel", "is_correct": False},
                        {"text": "Word", "is_correct": False},
                        {"text": "PowerPoint", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel outil utilise des boards Kanban ?",
                    "explanation": "Trello utilise des boards Kanban visuels.",
                    "choices": [
                        {"text": "Trello", "is_correct": True},
                        {"text": "Jira", "is_correct": False},
                        {"text": "Slack", "is_correct": False},
                        {"text": "Zoom", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce qui rend GitHub Projects unique ?",
                    "explanation": "GitHub Projects intègre directement le code, issues et PRs.",
                    "choices": [
                        {"text": "Il est gratuit", "is_correct": False},
                        {"text": "Il intègre le code et les issues", "is_correct": True},
                        {"text": "Il est en français", "is_correct": False},
                        {"text": "Il ne nécessite pas de compte", "is_correct": False},
                    ],
                },
                {
                    "title": "Qu'est-ce qui influence le choix d'un outil ?",
                    "explanation": "La taille de l'équipe, le budget, la complexité et les intégrations influencent le choix.",
                    "choices": [
                        {"text": "Uniquement le prix", "is_correct": False},
                        {"text": "Taille, budget, complexité et intégrations", "is_correct": True},
                        {"text": "Uniquement la couleur", "is_correct": False},
                        {"text": "Uniquement le nom", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Simulation de Sprint": {
        "contents": [
            {
                "title": "Simulation de Sprint : Mise en Pratique",
                "content_type": "markdown",
                "content": "# Simulation de Sprint\n\n## Objectif\n\nMettre en pratique Scrum via une simulation complète d'un sprint.\n\n## Étapes\n\n### 1. Sprint Planning (30 min)\n- Lire le Product Backlog\n- Estimer en story points\n- Sélectionner les items du sprint\n- Définir l'objectif du sprint\n\n### 2. Daily Scrum (5 min/jour)\n- Ce que j'ai fait\n- Ce que je vais faire\n- Obstacles\n\n### 3. Développement (simulation)\n- Répartir les tâches\n- Suivre le Sprint Backlog\n- Mettre à jour le burndown chart\n\n### 4. Sprint Review (20 min)\n- Démonstration\n- Feedback\n- Adaptation du backlog\n\n### 5. Sprint Retrospective (15 min)\n- Ce qui a bien fonctionné\n- Ce qui peut être amélioré\n- Plan d'action\n\n## Estimation\n\n### Planning Poker\n- Cartes : 1, 2, 3, 5, 8, 13, 21\n- Chacun vote simultanément\n- Discussion si divergence\n- Consensus\n\n## Burndown Chart\n\nGraphique montrant le travail restant dans le sprint.",
                "duration_minutes": 50,
            },
            {
                "title": "Vidéo : Simulation de Sprint Scrum",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 40,
            },
            {
                "title": "Ressource : Planning Poker Online",
                "content_type": "external",
                "resource_url": "https://planningpokeronline.com/",
                "duration_minutes": 15,
            },
        ],
        "quiz": {
            "title": "Quiz : Simulation de Sprint",
            "description": "Testez vos connaissances sur la simulation de sprint.",
            "questions": [
                {
                    "title": "Qu'est-ce que le Planning Poker ?",
                    "explanation": "Le Planning Poker est une technique d'estimation collective en story points.",
                    "choices": [
                        {"text": "Un jeu de cartes", "is_correct": False},
                        {"text": "Une technique d'estimation collective", "is_correct": True},
                        {"text": "Un outil de monitoring", "is_correct": False},
                        {"text": "Un type de réunion client", "is_correct": False},
                    ],
                },
                {
                    "title": "Que montre un burndown chart ?",
                    "explanation": "Le burndown chart montre le travail restant dans le sprint au fil du temps.",
                    "choices": [
                        {"text": "Le budget consommé", "is_correct": False},
                        {"text": "Le travail restant dans le sprint", "is_correct": True},
                        {"text": "Le nombre de bugs", "is_correct": False},
                        {"text": "La satisfaction client", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelles sont les 3 questions du Daily Scrum ?",
                    "explanation": "Qu'ai-je fait ? Que vais-je faire ? Y a-t-il des obstacles ?",
                    "choices": [
                        {"text": "Budget, planning, risques", "is_correct": False},
                        {"text": "Fait, à faire, obstacles", "is_correct": True},
                        {"text": "Qui, quoi, quand", "is_correct": False},
                        {"text": "Pourquoi, comment, combien", "is_correct": False},
                    ],
                },
                {
                    "title": "Quand se tient la Sprint Retrospective ?",
                    "explanation": "La rétrospective se tient à la fin du sprint, après la Sprint Review.",
                    "choices": [
                        {"text": "Au début du sprint", "is_correct": False},
                        {"text": "À la fin du sprint", "is_correct": True},
                        {"text": "Au milieu du sprint", "is_correct": False},
                        {"text": "Une fois par an", "is_correct": False},
                    ],
                },
            ],
        },
    },

    # ── Les Bases de Python (modules déjà peuplés par seed_courses) ──
    "Introduction à Python": {
        "contents": [
            {
                "title": "Vidéo : Introduction à Python",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 30,
            },
            {
                "title": "Ressource : Documentation officielle Python",
                "content_type": "external",
                "resource_url": "https://docs.python.org/fr/3/",
                "duration_minutes": 20,
            },
        ],
        "quiz": {
            "title": "Quiz : Introduction à Python",
            "description": "Testez vos connaissances sur l'introduction à Python.",
            "questions": [
                {
                    "title": "Qui a créé Python ?",
                    "explanation": "Python a été créé par Guido van Rossum en 1991.",
                    "choices": [
                        {"text": "Linus Torvalds", "is_correct": False},
                        {"text": "Guido van Rossum", "is_correct": True},
                        {"text": "Dennis Ritchie", "is_correct": False},
                        {"text": "James Gosling", "is_correct": False},
                    ],
                },
                {
                    "title": "Quelle est la philosophie de Python ?",
                    "explanation": "La philosophie de Python est 'Simple est mieux que complexe' (Zen of Python).",
                    "choices": [
                        {"text": "Rapide avant tout", "is_correct": False},
                        {"text": "Simple est mieux que complexe", "is_correct": True},
                        {"text": "Complexité pour performance", "is_correct": False},
                        {"text": "Tout en une ligne", "is_correct": False},
                    ],
                },
                {
                    "title": "Comment vérifier la version de Python ?",
                    "explanation": "python --version affiche la version installée.",
                    "choices": [
                        {"text": "python version", "is_correct": False},
                        {"text": "python --version", "is_correct": True},
                        {"text": "python -v", "is_correct": False},
                        {"text": "python info", "is_correct": False},
                    ],
                },
            ],
        },
    },

    "Variables et Types de Données": {
        "contents": [
            {
                "title": "Vidéo : Variables et Types en Python",
                "content_type": "video",
                "resource_url": "https://www.youtube.com/watch?v=placeholder",
                "duration_minutes": 35,
            },
            {
                "title": "Ressource : Tutoriel Python officiel",
                "content_type": "external",
                "resource_url": "https://docs.python.org/fr/3/tutorial/introduction.html",
                "duration_minutes": 20,
            },
        ],
        "quiz": {
            "title": "Quiz : Variables et Types de Données",
            "description": "Testez vos connaissances sur les variables et types Python.",
            "questions": [
                {
                    "title": "Comment crée-t-on une variable en Python ?",
                    "explanation": "On assigne une valeur avec le signe = : nom = valeur",
                    "choices": [
                        {"text": "var nom = valeur", "is_correct": False},
                        {"text": "nom = valeur", "is_correct": True},
                        {"text": "let nom = valeur", "is_correct": False},
                        {"text": "declare nom = valeur", "is_correct": False},
                    ],
                },
                {
                    "title": "Quel est le type de 3.14 ?",
                    "explanation": "3.14 est un nombre à virgule flottante (float).",
                    "choices": [
                        {"text": "int", "is_correct": False},
                        {"text": "float", "is_correct": True},
                        {"text": "str", "is_correct": False},
                        {"text": "bool", "is_correct": False},
                    ],
                },
                {
                    "title": "Comment vérifier le type d'une variable ?",
                    "explanation": "type() retourne le type d'une variable.",
                    "choices": [
                        {"text": "typeof(x)", "is_correct": False},
                        {"text": "type(x)", "is_correct": True},
                        {"text": "x.type", "is_correct": False},
                        {"text": "gettype(x)", "is_correct": False},
                    ],
                },
                {
                    "title": "Les chaînes de caractères en Python sont-elles mutables ?",
                    "explanation": "Les strings sont immuables (non modifiables) en Python.",
                    "choices": [
                        {"text": "Oui", "is_correct": False},
                        {"text": "Non, elles sont immuables", "is_correct": True},
                        {"text": "Uniquement en Python 2", "is_correct": False},
                        {"text": "Uniquement avec une bibliothèque", "is_correct": False},
                    ],
                },
            ],
        },
    },
}


class Command(BaseCommand):
    help = 'Seed automatique des contenus (lessons) et quiz pour tous les modules existants'

    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Recrée les contenus et quiz même s\'ils existent déjà')

    @transaction.atomic
    def handle(self, *args, **options):
        force = options.get('force', False)

        modules = Module.objects.all().select_related('course')
        if not modules.exists():
            self.stdout.write(self.style.WARNING('Aucun module trouvé en base. Lancez seed_courses d\'abord.'))
            return

        self.stdout.write(f'Trouvé {modules.count()} modules à traiter.')

        created_contents = 0
        created_quizzes = 0
        created_questions = 0
        created_choices = 0
        skipped = 0

        for module in modules:
            module_data = MODULE_DATA.get(module.title)

            if not module_data:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ Module "{module.title}" (cours: {module.course.title}) '
                        f'non trouvé dans le mapping — contenus génériques créés'
                    )
                )
                module_data = self._generic_data(module)

            # ─── Contenus ───
            existing_contents = module.contents.all()
            if existing_contents.exists() and not force:
                self.stdout.write(
                    f'  ✓ Module "{module.title}" — {existing_contents.count()} contenu(s) déjà existant(s), ignoré'
                )
                skipped += 1
            else:
                if force and existing_contents.exists():
                    existing_contents.delete()
                    self.stdout.write(f'  🗑 Module "{module.title}" — contenus existants supprimés (--force)')

                for content_data in module_data.get('contents', []):
                    Content.objects.create(
                        module=module,
                        title=content_data['title'],
                        content_type=content_data['content_type'],
                        resource_url=content_data.get('resource_url'),
                        content=content_data.get('content'),
                        duration_minutes=content_data.get('duration_minutes'),
                    )
                    created_contents += 1
                    self.stdout.write(
                        f'  + Contenu créé : {content_data["title"]} ({content_data["content_type"]})'
                    )

            # ─── Quiz ───
            has_quiz = hasattr(module, 'quiz') and module.quiz is not None
            quiz_data = module_data.get('quiz')

            if quiz_data:
                if has_quiz and not force:
                    self.stdout.write(
                        f'  ✓ Module "{module.title}" — quiz déjà existant, ignoré'
                    )
                else:
                    if has_quiz and force:
                        module.quiz.delete()

                    quiz = Quiz.objects.create(
                        module=module,
                        title=quiz_data['title'],
                        description=quiz_data.get('description', ''),
                    )
                    created_quizzes += 1
                    self.stdout.write(f'  + Quiz créé : {quiz_data["title"]}')

                    for q_data in quiz_data.get('questions', []):
                        question = QuizQuestion.objects.create(
                            quiz=quiz,
                            title=q_data['title'],
                            explanation=q_data.get('explanation', ''),
                        )
                        created_questions += 1

                        for c_data in q_data.get('choices', []):
                            QuizChoice.objects.create(
                                question=question,
                                text=c_data['text'],
                                is_correct=c_data.get('is_correct', False),
                            )
                            created_choices += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('─' * 50))
        self.stdout.write(self.style.SUCCESS(f'Résumé :'))
        self.stdout.write(self.style.SUCCESS(f'  Contenus créés  : {created_contents}'))
        self.stdout.write(self.style.SUCCESS(f'  Quiz créés      : {created_quizzes}'))
        self.stdout.write(self.style.SUCCESS(f'  Questions créées: {created_questions}'))
        self.stdout.write(self.style.SUCCESS(f'  Choix créés     : {created_choices}'))
        self.stdout.write(self.style.SUCCESS(f'  Modules ignorés : {skipped}'))
        self.stdout.write(self.style.SUCCESS('─' * 50))

    def _generic_data(self, module):
        """Génère des contenus génériques pour les modules non mappés."""
        return {
            "contents": [
                {
                    "title": f"Introduction : {module.title}",
                    "content_type": "markdown",
                    "content": f"# {module.title}\n\n## Introduction\n\nCe module couvre les concepts essentiels de **{module.title}** dans le cadre de la formation **{module.course.title}**.\n\n## Objectifs\n\n- Comprendre les fondamentaux\n- Mettre en pratique les concepts\n- Appliquer les bonnes pratiques\n\n## Plan du module\n\n1. Concepts théoriques\n2. Démonstration pratique\n3. Exercices et ressources",
                    "duration_minutes": 30,
                },
                {
                    "title": f"Vidéo : {module.title}",
                    "content_type": "video",
                    "resource_url": "https://www.youtube.com/watch?v=placeholder",
                    "duration_minutes": 40,
                },
                {
                    "title": f"Ressources : {module.title}",
                    "content_type": "external",
                    "resource_url": "https://www.google.com/search?q=" + module.title.replace(' ', '+'),
                    "duration_minutes": 20,
                },
            ],
            "quiz": {
                "title": f"Quiz : {module.title}",
                "description": f"Testez vos connaissances sur {module.title}.",
                "questions": [
                    {
                        "title": f"Quelle est la principale compétence visée par le module '{module.title}' ?",
                        "explanation": f"Ce module vise à maîtriser les concepts de {module.title}.",
                        "choices": [
                            {"text": "Comprendre les fondamentaux", "is_correct": True},
                            {"text": "Mémoriser des dates historiques", "is_correct": False},
                            {"text": "Apprendre une langue étrangère", "is_correct": False},
                            {"text": "Pratiquer un sport", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Quelle est la meilleure approche pour apprendre efficacement ?",
                        "explanation": "La pratique régulière et la mise en situation sont les plus efficaces.",
                        "choices": [
                            {"text": "Lire uniquement la théorie", "is_correct": False},
                            {"text": "Pratiquer régulièrement", "is_correct": True},
                            {"text": "Regarder uniquement des vidéos", "is_correct": False},
                            {"text": "Ne rien faire", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Pourquoi est-il important de pratiquer ?",
                        "explanation": "La pratique permet de consolider les acquis et de découvrir des cas concrets.",
                        "choices": [
                            {"text": "Pour gagner du temps", "is_correct": False},
                            {"text": "Pour consolider les acquis", "is_correct": True},
                            {"text": "Pour éviter d'apprendre", "is_correct": False},
                            {"text": "Pour impressionner", "is_correct": False},
                        ],
                    },
                ],
            },
        }
