from collections import defaultdict
from random import shuffle

from django.db import transaction
from django.db.models import Case, When, IntegerField

from accounts.models import User
from challenges.models import Challenge, Settings, PersonalityChallenge
from questions.models import Question, Tag
from wib_challenge.enums import ExperienceLevel


def select_questions(skills: list[Tag] | None = None):
    QUESTION_QUOTAS = {
        Question.QuestionType.MULTIPLE_CHOICE: 14,
        Question.QuestionType.OPEN_ANSWER: 6,
        # Question.QuestionType.UNIQUE_CHOICE: 5,
    }
    questions = []
    for skill in skills:
        skill_questions = skill.questions.all()  # (level__lte=F('tags__user_skills__experience_level'))
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

        selected_questions = []
        remaining_needed = sum(QUESTION_QUOTAS.values())

        for q_type, count in QUESTION_QUOTAS.items():
            selected = questions_by_type[q_type][:count]
            selected_questions.extend(selected)
            remaining_needed -= len(selected)

        if remaining_needed > 0:
            remaining_questions = [
                q for qt, qs in questions_by_type.items()
                for q in qs if q not in selected_questions
            ]
            shuffle(remaining_questions)
            selected_questions.extend(remaining_questions[:remaining_needed])

        questions.extend(selected_questions)

    return questions


@transaction.atomic
def generate_challenge_for_user(user: User, skills: list[Tag] | None = None):
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
        description=f'Testez vos compétences pour {user.domain.name}',
        duration=challenge_duration
    )
    selected_questions = select_questions(skills or list(user.skills.all()))
    challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.save()
    return challenge


@transaction.atomic
def generate_personality_challenge_for_user(user: User):
    challenge = PersonalityChallenge.objects.create(
        title=f'Test de Personnalité pour {user.get_full_name()}',
        description="Ce test nous permet de mieux vous connaitre",
        candidate=user
    )
    selected_questions = select_questions([Tag.objects.filter(name__icontains='Test de personnalité').first()])
    challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.save()
    return challenge


@transaction.atomic
def generate_logical_challenge_for_user(user: User):
    challenge = Challenge.objects.create(
        domain=user.domain,
        title=f'Test de Logique pour {user.get_full_name()}',
        description='Test de logique',
        duration=Settings.objects.first().default_challenge_duration
    )
    selected_questions = select_questions([Tag.objects.filter(name__icontains='Test logique').first()])
    challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.is_logical = True
    challenge.save()
    return challenge

# TODO check data constraint when importing questions
# TODO make admin site more user-friendly with lastest databases changes
