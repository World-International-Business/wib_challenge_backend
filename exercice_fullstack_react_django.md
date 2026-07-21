# Exercice technique Full-Stack : Gestionnaire de tâches

## Contexte

Le candidat doit implémenter une petite application de gestion de tâches (Todo List) avec un backend **Django + Django REST Framework** et un frontend **React**.

## Objectif

Créer une application permettant à un utilisateur authentifié de :

1. S'inscrire / se connecter.
2. Voir la liste de ses tâches.
3. Ajouter une nouvelle tâche.
4. Marquer une tâche comme terminée / non terminée.
5. Supprimer une tâche.
6. Filtrer les tâches par statut (toutes / actives / terminées).

## Stack technique

- **Backend** : Django 5.x + Django REST Framework + SQLite (ou PostgreSQL)
- **Frontend** : React 18 + Vite + Fetch/Axios + CSS modules ou Tailwind
- **Authentification** : JWT (SimpleJWT) ou sessions selon préférence

## Backend — endpoints API

### Modèle `Task`

```python
class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Endpoints attendus

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/register/` | Créer un compte |
| POST | `/api/auth/login/` | Obtenir un token JWT |
| GET | `/api/tasks/` | Lister les tâches de l'utilisateur connecté |
| POST | `/api/tasks/` | Créer une tâche |
| PATCH | `/api/tasks/<id>/` | Modifier le statut ou le titre |
| DELETE | `/api/tasks/<id>/` | Supprimer une tâche |

### Contraintes backend

- Chaque utilisateur ne voit que **ses propres** tâches.
- Les endpoints nécessitent une authentification (sauf register/login).
- Réponses JSON propres avec messages d'erreur explicites.

## Frontend — fonctionnalités

### Pages / composants

- **Login / Register** : formulaires simples avec validation basique.
- **TaskList** : affichage des tâches sous forme de liste ou cartes.
- **TaskForm** : champ pour ajouter une tâche rapidement.
- **TaskItem** : titre, statut, boutons "terminer" et "supprimer".
- **FilterBar** : filtres "Toutes / Actives / Terminées".

### Contraintes frontend

- Utiliser React avec hooks (`useState`, `useEffect`).
- Gérer le token JWT dans le `localStorage`.
- Intercepter les erreurs 401 et rediriger vers la page de login.
- Interface responsive et propre.

## Bonus (optionnels)

- Pagination ou infinite scroll.
- Tests unitaires backend avec pytest / Django TestCase.
- Tests frontend avec Vitest / React Testing Library.
- Déploiement backend sur Render / Railway et frontend sur Vercel.
- Dockerisation du projet.

## Livrables attendus

1. Lien vers un dépôt GitHub contenant le backend et le frontend.
2. README avec instructions d'installation (`pip install`, `npm install`, etc.).
3. Durée estimée : **2 à 3 heures**.

## Critères d'évaluation

| Critère | Poids |
|---------|-------|
| Fonctionnalités complètes | 30 % |
| Qualité du code (structure, nommage) | 25 % |
| Sécurité & authentification | 20 % |
| Interface utilisateur | 15 % |
| README / documentation | 10 % |

## Rappel pour le candidat

> Privilégiez la simplicité et la clarté. Un projet fonctionnel et bien structuré vaut mieux qu'un projet surchargé.
