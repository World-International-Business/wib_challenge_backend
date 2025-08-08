from typing import List

from pydantic import BaseModel, Field

from apps.core.models import Profession
from services.utils import get_genai_client, GEMINI_MODEL


class ChoiceModel(BaseModel):
    text: str = Field(..., description="Texte du choix")


class QuestionModel(BaseModel):
    text: str = Field(..., description="Texte de la question")
    choices: List[ChoiceModel] = Field(..., description="Liste des choix")


class PersonalityTestModel(BaseModel):
    theme: str = Field(..., description="courte description sur les thématiques identifiées")
    questions: List[QuestionModel] = Field(..., description="Liste des 30 questions", min_length=30, max_length=30)


def generate_evaluation(
        profession: Profession,
        experience_level: str,
        description: str
) -> PersonalityTestModel:
    prompt = f"""Tu es un expert en psychologie organisationnelle et en évaluation des compétences comportementales.

CONTEXTE PROFESSIONNEL:
- Poste: {profession.title}
- Domaine: {profession.domain.name}
- Niveau d'expérience requis: {experience_level}
- Description détaillée du poste: {description}

MISSION:
Analyse la description du poste et génère exactement 30 questions d'analyse de personnalité adaptées à ce contexte spécifique.

CONSIGNES DÉTAILLÉES:
1. IDENTIFIER LES THÉMATIQUES: Analyse la description du poste pour identifier 5-6 thématiques comportementales clés nécessaires pour ce rôle (ex: leadership, créativité, rigueur, collaboration, autonomie, communication, gestion du stress, innovation, etc.)

2. RÉPARTIR LES QUESTIONS: Distribue les 30 questions de manière équilibrée entre ces thématiques (environ 5-6 questions par thématique)

3. ADAPTER LES THÉMATIQUES au niveau {experience_level}

4. CONTEXTUALISER: Utilise des situations concrètes liées au poste de {profession.title} dans le domaine {profession.domain.name}

TYPES DE QUESTIONS À VARIER:
- Situations professionnelles hypothétiques spécifiques au domaine
- Auto-évaluation comportementale
- Préférences de travail et méthodologies
- Réactions face aux défis techniques et humains
- Style de communication et collaboration en équipe

EXIGENCES STRICTES:
- Exactement 30 questions
- Chaque question a exactement 4 choix
- Les choix doivent être nuancés, réalistes et non évidents
- Vocabulaire technique adapté au niveau {experience_level}
- Questions progressives en complexité selon l'expérience
- Situations concrètes basées sur la description du poste
- Chaque thématique doit avoir entre 5 et 6 questions

Génère maintenant le test de personnalité:"""

    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                'temperature': 0.7,
                'max_output_tokens': 4096,
                'response_mime_type': 'application/json',
                'response_schema': list[QuestionModel],
            }
        )

        return response.parsed

    except Exception as e:
        raise Exception(f"Erreur lors de la génération des questions de personnalité: {str(e)}")
