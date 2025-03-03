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
        parser.add_argument('--userId', type=int, help='UserId')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        path = Path(__file__).resolve().parent
        data = json.loads(open(path / 'data.json', encoding='utf8').read())

        domain = Domain.objects.create(**data['domains'][0])
        self.stdout.write(self.style.SUCCESS('Creating Domain {}'.format(domain)))

        questions = []

        for q in data['questions']:
            question = Question.objects.create(
                **q
            )
            questions.append(question)
            self.stdout.write(self.style.SUCCESS('Creating Question {}'.format(question)))

        # Create Choices
        for choice_data in data['choices']:
            Choice.objects.create(
                **choice_data
            )
            self.stdout.write(self.style.SUCCESS('Creating Choice {}'.format(choice_data)))

        # Create Challenge
        challenge_questions = data['challenges'][0].pop('questions')
        duration = data['challenges'][0].pop('duration')
        challenge = Challenge.objects.create(
            **data['challenges'][0]

        )
        challenge.questions.set(challenge_questions)  # Set related questions
        self.stdout.write(self.style.SUCCESS('Creating Challenge {}'.format(challenge)))
        self.stdout.write(
            self.style.SUCCESS('Adding Questions {} to Challenge {}'.format(challenge_questions, challenge)))

        if not kwargs['submission'] or not kwargs['userId']:
            return

        # Create Submission
        submission = Submission.objects.create(
            challenge=challenge,
            candidate_id=kwargs['userId'],
            result=data['submissions'][0]['result'],
            submitted_at=timezone.make_aware(
                datetime.datetime.fromisoformat(data['submissions'][0]['submitted_at'][:-1]))
        )

        self.stdout.write(self.style.SUCCESS('Creating Submission {}'.format(submission)))

        # Create Answers
        for answer_data in data['submissions'][0]['answers']:
            question = questions[answer_data['question_id'] - 1]  # Adjust index if needed
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
