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


def select_questions(skills: list[Tag] | None = None, question_category: str = Question.QuestionCategory.NORMAL, domain: Domain = None):
    settings = Settings.objects.first()
    if settings:
        question_quotas = {
            Question.QuestionType.MULTIPLE_CHOICE: settings.multiple_choice_question_count_per_tag,
            Question.QuestionType.OPEN_ANSWER: settings.open_answer_question_count_per_tag,
            Question.QuestionType.UNIQUE_CHOICE: settings.unique_choice_question_count_per_tag,
        }
    else:
        question_quotas = {
            Question.QuestionType.MULTIPLE_CHOICE: 3,
            Question.QuestionType.OPEN_ANSWER: 5,
            Question.QuestionType.UNIQUE_CHOICE: 2,
        }

    question_queryset = Question.objects.filter(question_category=question_category)
    if domain:
        # A domain includes every category and tag below it. Candidate skills
        # must not hide questions authored for another sub-competence.
        question_queryset = question_queryset.filter(category__domain=domain)
    elif skills:
        question_queryset = question_queryset.filter(tags__in=skills).distinct()

    questions_by_type = defaultdict(list)
    for question in question_queryset:
        questions_by_type[question.question_type].append(question)

    selected_questions = []
    for question_type, count in question_quotas.items():
        candidates = questions_by_type[question_type]
        shuffle(candidates)
        selected_questions.extend(candidates[:count])

    return selected_questions


@transaction.atomic
def generate_challenge_for_user(user: User, skills: list[Tag] | None = None):
    durations = get_profile_durations(user.domain, user.experience_level)

    challenge = Challenge.objects.create(
        domain=user.domain,
        title=f'Test de {user.domain.name} pour {user.get_full_name()}',
        description=f'Testez vos compétences pour {user.domain.name}',
        duration=durations['technical']
    )
    selected_questions = select_questions(skills or list(user.skills.all()), domain=user.domain)
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
    selected_questions = select_questions(
        list(Tag.objects.filter(
            questions__question_category=Question.QuestionCategory.PERSONALITY,
            questions__category__domain=domain,
        ).distinct()),
        question_category=Question.QuestionCategory.PERSONALITY,
        domain=domain,
    )
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
    selected_questions = select_questions(
        list(Tag.objects.filter(
            questions__question_category=Question.QuestionCategory.LOGICAL,
            questions__category__domain=user.domain,
        ).distinct()),
        question_category=Question.QuestionCategory.LOGICAL,
        domain=user.domain,
    )
    challenge.questions.add(*selected_questions)
    challenge.title += ' #' + str(challenge.pk)
    challenge.is_logical = True
    challenge.save()
    return challenge

# TODO check data constraint when importing questions
# TODO make admin site more user-friendly with lastest databases changes
