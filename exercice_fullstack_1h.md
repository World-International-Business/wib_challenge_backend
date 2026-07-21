# Exercice technique Full-Stack — 1 heure

## Contexte

Ce test vise à évaluer la capacité du candidat à **livrer proprement, rapidement et intelligemment**, avec un usage pertinent des outils d'IA.

## Objectif

Implémenter une **mini Todo List** en 3 étapes : correction, ajout de fonctionnalité, documentation.

## Stack imposée

- **Backend** : Django + Django REST Framework
- **Frontend** : React
- **Base de données** : SQLite (locale)

## Partie 1 — Correction rapide (20 min)

On fournit un starter contenant deux bugs intentionnels :

1. **Backend** : l'endpoint `/api/tasks/` retourne toutes les tâches sans filtrer (manque `request.user`).
2. **Frontend** : le formulaire d'ajout soumet une tâche vide sans vérification.

**Mission** : corriger les bugs et expliquer brièvement en commentaire ce qui posait problème.

## Partie 2 — Ajout de fonctionnalité (30 min)

Ajouter la possibilité de **filtrer les tâches** côté frontend :

- Toutes
- Actives
- Terminées

Le filtre doit être fait côté frontend (pas d'appel API supplémentaire).

### Critères attendus

- Code lisible et nommé explicitement.
- Aucune répétition inutile.
- Composants React petits et réutilisables.
- Pas de console.log oubliés.
- Gestion des erreurs basique (try/catch ou `.catch`).

## Partie 3 — Utilisation de l'IA (10 min)

Dans un fichier `IA_USAGE.md`, le candidat doit répondre aux questions suivantes :

1. Quelles parties as-tu confiées à l'IA ?
2. Quels prompts as-tu utilisés ? Donne un exemple concret.
3. Quelles vérifications as-tu faites sur le code généré ?
4. Quelle est la limite que tu fixes à l'usage de l'IA dans un projet pro ?

## Livrables

- Dépôt GitHub (ou ZIP) contenant le backend et le frontend.
- Fichier `README.md` avec instructions d'installation en 3 commandes maximum.
- Fichier `IA_USAGE.md` rempli.

## Durée

**45 min à 1h maximum.**

## Critères d'évaluation

| Critère | Poids |
|---------|-------|
| Correction des bugs | 25 % |
| Fonctionnalité filtre | 25 % |
| Qualité du code | 25 % |
| Usage pertinent de l'IA | 15 % |
| README clair | 10 % |

## Message pour le candidat

> Pas besoin de design parfait ni de fonctionnalités avancées. On cherche du code propre, une logique solide et un usage raisonné de l'IA comme assistant, pas comme remplacement de la réflexion.
