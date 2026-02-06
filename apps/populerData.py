import json
from pathlib import Path

from django.contrib.auth import get_user_model

from apps.questions.models import Question, Choice
from apps.core.models import Technology  # si tu veux fixer une techno, sinon tu peux supprimer

User = get_user_model()


def run():
    # 1) Chemin vers le JSON (au niveau de manage.py)
    json_path = Path("chef_project_industrielle_personnalite.json")

    if not json_path.exists():
        raise FileNotFoundError(f"Fichier JSON introuvable : {json_path.resolve()}")

    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Le JSON doit contenir une liste de questions (un tableau [...]).")

    # 2) Récupérer le user de l'organisation qui publie les questions
    # À ADAPTER : mets l'email du compte entreprise / org
    publisher = User.objects.get(email="wib@gmail.com")

    # 3) (Optionnel) fixer une technologie commune pour toutes les questions
    # Si tu n'as pas besoin de techno, mets 'technology = None'
    # Sinon, récupère une Technology existante (ex: 'Assistante de direction')
    try:
        technology = Technology.objects.get(name="chef de Project industrielle")
    except Technology.DoesNotExist:
        technology = None  # ou lève une erreur si tu veux que ce soit obligatoire

    created_count = 0

    for q_data in data:
        # Extraire les choix depuis le JSON
        choices_data = q_data.pop("choices", [])

        # Normaliser les clés des choix : isCorrect -> is_correct
        normalized_choices = []
        for c in choices_data:
            normalized_choices.append(
                {
                    "text": c["text"],
                    "is_correct": c.get("isCorrect", False),
                }
            )

        # Option : forcer le statut publié, ou laisser le statut du JSON
        q_data.pop("status", None)  # on enlève le status du JSON
        # Tu peux aussi garder status = q_data.get("status") si tu préfères

        # Création de la question
        question = Question.objects.create(
            publisher=publisher,
            technology=technology,
            status=Question.Status.PUBLISHED,
            **q_data,  # title, description, explanation, difficulty, duration, etc.
        )

        # Création des choix en bulk (rapide)
        Choice.objects.bulk_create(
            [Choice(question=question, **c) for c in normalized_choices]
        )

        created_count += 1

        # comment execulter le script
            # from apps.populerData import run
            # run()

    print(f"{created_count} questions créées avec succès pour l'organisation {publisher.email}.")