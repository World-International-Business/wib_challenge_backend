from collections import defaultdict
from random import shuffle

from django.db import transaction
from django.db.models import Case, When, IntegerField

from accounts.models import User
from challenges.models import Challenge, Settings, PersonalityChallenge, TestDurationProfile
from questions.models import Question, Tag, Domain
from wib_challenge.enums import ExperienceLevel


def get_profile_durations(domain, experience_level):
    profile = TestDurationProfile.objects.filter(domain=domain, experience_level=experience_level).first()
    if not profile:
        return {
            'technical': Settings.objects.first().default_challenge_duration,
            'logical': Settings.objects.first().default_challenge_duration,
            'personality': Settings.objects.first().default_challenge_duration,
        }
    return {
        'technical': profile.technical_duration,
        'logical': profile.logical_duration,
        'personality': profile.personality_duration,
    }


def select_questions(skills: list[Tag] | None = None, question_category: str = Question.QuestionCategory.NORMAL):
    question_quotas = {
        Question.QuestionType.MULTIPLE_CHOICE: 14,
        Question.QuestionType.OPEN_ANSWER: 6,
        # Question.QuestionType.UNIQUE_CHOICE: 5,
    }
    questions = []
    for skill in skills:
        skill_questions = skill.questions.filter(
            question_category=question_category)  # Filtrer par catégorie de question
        queryset = skill_questions.annotate(
            type_priority=Case(
                *[When(question_type=qt, then=idx)
                  for idx, qt in enumerate(question_quotas.keys())],
                default=len(question_quotas),
                output_field=IntegerField()
            )
        ).order_by('type_priority')

        questions_by_type = defaultdict(list)
        for question in queryset:
            questions_by_type[question.question_type].append(question)

        selected_questions = []
        remaining_needed = sum(question_quotas.values())

        for q_type, count in question_quotas.items():
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
    durations = get_profile_durations(user.domain, user.experience_level)

    challenge = Challenge.objects.create(
        domain=user.domain,
        title=f'Test de {user.domain.name} pour {user.get_full_name()}',
        description=f'Testez vos compétences pour {user.domain.name}',
        duration=durations['technical']
    )
    selected_questions = select_questions(skills or list(user.skills.all()))
    challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.save()
    return challenge


@transaction.atomic
def generate_personality_challenge_for_user(user: User, domain: Domain):
    durations = get_profile_durations(domain, user.experience_level)
    challenge = PersonalityChallenge.objects.create(
        title=f'Test de Personnalité pour {user.get_full_name()}',
        description="Ce test nous permet de mieux vous connaitre",
        candidate=user,
        duration=durations['personality']
    )
    selected_questions = select_questions(list(Tag.objects.filter(questions__question_category=Question.QuestionCategory.PERSONALITY,
                                                                  criteria__category__domain=domain).distinct()), question_category=Question.QuestionCategory.PERSONALITY)
    challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.save()
    return challenge


@transaction.atomic
def generate_logical_challenge_for_user(user: User):
    durations = get_profile_durations(user.domain, user.experience_level)
    challenge = Challenge.objects.create(
        domain=user.domain,
        title=f'Test Psychotechnique pour {user.get_full_name()}',
        description='Test Psychotechnique',
        duration=durations['logical']
    )
    selected_questions = select_questions(list(Tag.objects.filter(questions__question_category=Question.QuestionCategory.LOGICAL).distinct()),
                                          question_category=Question.QuestionCategory.LOGICAL)
    challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.is_logical = True
    challenge.save()
    return challenge

# TODO check data constraint when importing questions
# TODO make admin site more user-friendly with lastest databases changes
