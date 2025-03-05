import datetime
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from challenges.models import Answer, Domain, Question, Choice, Challenge, Submission  # Adjust 'myapp' to your app name


class Command(BaseCommand):
    help = 'Create Default Fake Data'

    def add_arguments(self, parser):
        parser.add_argument('--submission', action='store_true', help='Create Submission')
        parser.add_argument('--challenge', action='store_true', help='Create Challenge')
        parser.add_argument('--userId', type=int, help='UserId')
        parser.add_argument('--question_type', type=str, help='Type de question')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        path = Path(__file__).resolve().parent
        data = json.loads(open(path / 'data.json', encoding='utf8').read())

        domain, _ = Domain.objects.get_or_create(**data['domains'][0])
        self.stdout.write(self.style.SUCCESS('Creating Domain {}'.format(domain)))

        questions = []

        for q in data['questions']:
            if bool(kwargs['question_type']) and kwargs['question_type'] != q['question_type']:
                continue
            question, _ = Question.objects.get_or_create(
                **q
            )
            questions.append(question)
            self.stdout.write(self.style.SUCCESS('Creating Question {}'.format(question)))

        questions_ids = [question.id for question in questions]
        for choice_data in data['choices']:
            if choice_data['question_id'] not in questions_ids:
                continue
            Choice.objects.get_or_create(
                **choice_data
            )
            self.stdout.write(self.style.SUCCESS('Creating Choice {}'.format(choice_data)))

        if not kwargs['challenge']:
            return
        # Create Challenge
        challenge_questions = data['challenges'][0].pop('questions')
        duration = data['challenges'][0].pop('duration')
        challenge, _ = Challenge.objects.get_or_create(
            **data['challenges'][0]

        )
        challenge_questions = [_id for _id in challenge_questions if _id in questions_ids]
        challenge.questions.set(challenge_questions)  # Set related questions
        self.stdout.write(self.style.SUCCESS('Creating Challenge {}'.format(challenge)))
        self.stdout.write(
            self.style.SUCCESS('Adding Questions {} to Challenge {}'.format(challenge_questions, challenge)))

        if not kwargs['submission'] or not kwargs['userId']:
            return

        # Create Submission
        submission, _ = Submission.objects.get_or_create(
            challenge=challenge,
            candidate_id=kwargs['userId'],
            result=data['submissions'][0]['result'],
            submitted_at=timezone.make_aware(
                datetime.datetime.fromisoformat(data['submissions'][0]['submitted_at'][:-1]))
        )

        self.stdout.write(self.style.SUCCESS('Creating Submission {}'.format(submission)))

        # Create Answers
        for answer_data in data['submissions'][0]['answers']:
            try:
                question = questions[answer_data['question_id'] - 1]  # Adjust index if needed
            except IndexError:
                continue
            answer = Answer.objects.create(
                submission=submission,
                question=question,
                text=answer_data['text'],
                is_correct=answer_data.get('is_correct'),
                answered_at=timezone.make_aware(datetime.datetime.fromisoformat(answer_data['answered_at'][:-1]))
            )
            self.stdout.write(self.style.SUCCESS('Creating Answer {}'.format(answer)))

            # Set selected choices
            for choice_index in answer_data['selected_choices']:
                choice = Choice.objects.filter(question=question)[choice_index - 1]  # Adjust index if needed
                answer.selected_choices.add(choice)
                self.stdout.write(self.style.SUCCESS('Adding Choice {} to Answer {}'.format(choice, answer)))
