from collections import defaultdict
from random import shuffle

from django.db import transaction
from django.db.models import Case, When, IntegerField, F

from accounts.models import User
from challenges.models import Challenge, Settings
from questions.models import Question
from wib_challenge.enums import ExperienceLevel


@transaction.atomic
def generate_challenge_for_user(user: User):
    settings = Settings.objects.first()
    challenge_duration = settings.default_challenge_duration
    if user.experience_level == ExperienceLevel.BEGINNER:
        challenge_duration = settings.beginner_challenge_duration
    elif user.experience_level == ExperienceLevel.INTERMEDIATE:
        challenge_duration = settings.intermediate_challenge_duration
    elif user.experience_level == ExperienceLevel.EXPERT:
        challenge_duration = settings.advanced_challenge_duration

    challenge = Challenge.objects.create(
        domain=user.domain,
        title=f'Test de {user.domain.name} pour {user.get_full_name()}',
        description=f'Testez vos compétences en {user.domain.name}',
        duration=challenge_duration
    )
    QUESTION_QUOTAS = {
        Question.QuestionType.MULTIPLE_CHOICE: 5,
        Question.QuestionType.OPEN_ANSWER: 3,
        Question.QuestionType.UNIQUE_CHOICE: 2,
    }
    for skill in user.skills.all():
        skill_questions = skill.questions.filter(level__lte=F('tags__user_skills__experience_level'))
        queryset = skill_questions.annotate(
            type_priority=Case(
                *[When(question_type=qt, then=idx) for idx, qt in enumerate(QUESTION_QUOTAS.keys())],
                default=len(QUESTION_QUOTAS),
                output_field=IntegerField()
            )
        ).order_by('type_priority')

        questions_by_type = defaultdict(list)
        for question in queryset:
            questions_by_type[question.question_type].append(question)

        # Étape 3 : Sélectionner les questions prioritaires
        selected_questions = []
        remaining_needed = sum(QUESTION_QUOTAS.values())

        for q_type, count in QUESTION_QUOTAS.items():
            selected = questions_by_type[q_type][:count]
            selected_questions.extend(selected)
            remaining_needed -= len(selected)

        # Étape 4 : Compléter avec d'autres questions si nécessaire
        if remaining_needed > 0:
            remaining_questions = [
                q for qt, qs in questions_by_type.items() if qt not in QUESTION_QUOTAS
                for q in qs
            ]
            shuffle(remaining_questions)  # Mélanger pour plus d'équité
            selected_questions.extend(remaining_questions[:remaining_needed])

        # Résultat final
        print(selected_questions)
        challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.save()
    return challenge

# TODO check data constraint when importing questions
# TODO make admin site more user-friendly with lastest databases changes