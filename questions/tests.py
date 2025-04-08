from rest_framework import status
from rest_framework.reverse import reverse_lazy
from rest_framework.test import APITestCase

from accounts.models import User
from core.models import Technology, Profession, Language
from evaluations.models import Evaluation
from questions.models import Question
from questions.serializers import QuestionSerializer


class QuestionTestCase(APITestCase):

    def setUp(self):
        self.technology = Technology.objects.create(name='Technology')
        self.user = User.objects.create(email='a@a', password='password')
        self.profession = Profession.objects.create(title='Developer Fullstack')
        self.profession.technologies.add(self.technology)
        self.evaluation = Evaluation.objects.create(title='Evaluation', technology=self.technology,
                                                    profession=self.profession)
        self.url = reverse_lazy('evaluations:questions-list', args=[self.evaluation.pk])
        self.url_detail = reverse_lazy('evaluations:questions-detail', args=[self.evaluation.pk, 1])
        questions = [
            {
                'text': 'Question 1',
                'technology': self.technology.pk,
                'language': Language.ENGLISH,
                'difficulty': Question.Difficulty.EASY,
                'explanation': 'Explanation 1',
                'choices': [
                    {'text': 'Choice 1', 'is_correct': True},
                    {'text': 'Choice 2', 'is_correct': False},
                    {'text': 'Choice 3', 'is_correct': False},
                    {'text': 'Choice 4', 'is_correct': False},
                ],
            },
            {
                'text': 'Question 2',
                'technology': self.technology.pk,
                'language': Language.ENGLISH,
                'difficulty': Question.Difficulty.MEDIUM,
                'explanation': 'Explanation 2',
                'choices': [
                    {'text': 'Choice 1', 'is_correct': False},
                    {'text': 'Choice 2', 'is_correct': True},
                    {'text': 'Choice 3', 'is_correct': False},
                    {'text': 'Choice 4', 'is_correct': False},
                ],
            },
            {
                'text': 'Question 3',
                'technology': self.technology.pk,
                'language': Language.ENGLISH,
                'difficulty': Question.Difficulty.HARD,
                'explanation': 'Explanation 3',
                'choices': [
                    {'text': 'Choice 1', 'is_correct': False},
                    {'text': 'Choice 2', 'is_correct': False},
                    {'text': 'Choice 3', 'is_correct': True},
                    {'text': 'Choice 4', 'is_correct': False},
                ],
            },
            {
                'text': 'Question 4',
                'technology': self.technology.pk,
                'language': Language.ENGLISH,
                'difficulty': Question.Difficulty.EXPERT,
                'explanation': 'Explanation 4',
                'choices': [
                    {'text': 'Choice 1', 'is_correct': False},
                    {'text': 'Choice 2', 'is_correct': False},
                    {'text': 'Choice 3', 'is_correct': False},
                    {'text': 'Choice 4', 'is_correct': True},
                ],
            },
        ]
        self.questions = []
        for question in questions:
            serializer = QuestionSerializer(data={**question, 'evaluation': self.evaluation.pk})
            serializer.is_valid(raise_exception=True)
            self.questions.append(serializer.save(publisher=self.user))
        self.client.force_authenticate(user=self.user)

    def test_create_question(self):
        data = {
            'text': 'New Question',
            'technology': self.technology.pk,
            'language': Language.ENGLISH,
            'evaluation': self.evaluation.pk,
            'difficulty': Question.Difficulty.EASY,
            'explanation': 'Explanation for new question',
            'choices': [
                {'text': 'Choice 1', 'is_correct': True},
                {'text': 'Choice 2', 'is_correct': False},
                {'text': 'Choice 3', 'is_correct': False},
                {'text': 'Choice 4', 'is_correct': False},
            ],
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        question = Question.objects.get(pk=response.data['id'])
        self.assertEqual(question.text, data['text'])
        self.assertEqual(question.language, data['language'])
        self.assertEqual(question.difficulty, data['difficulty'])
        self.assertEqual(question.explanation, data['explanation'])
        self.assertEqual(question.publisher, self.user)
        self.assertEqual(question.technology, self.technology)
        self.assertEqual(question.choices.count(), len(data['choices']))
        for choice_data in data['choices']:
            choice = question.choices.get(text=choice_data['text'])
            self.assertEqual(choice.is_correct, choice_data['is_correct'])

    def test_create_question_with_translation(self):
        data = {
            'text': 'New Question',
            'language': Language.ENGLISH,
            'evaluation': self.evaluation.pk,
            'difficulty': Question.Difficulty.EASY,
            'duration': 30,
            'explanation': 'Explanation for new question',
            'choices': [
                {'text': 'Choice 1', 'is_correct': True},
                {'text': 'Choice 2', 'is_correct': False},
                {'text': 'Choice 3', 'is_correct': False},
                {'text': 'Choice 4', 'is_correct': False},
            ],
            'translated': {
                'text': 'New Question',
                'language': Language.FRENCH,
                'explanation': 'Explanation for new question',
                'choices': [
                    {'text': 'Choice 1', 'is_correct': True},
                    {'text': 'Choice 2', 'is_correct': False},
                    {'text': 'Choice 3', 'is_correct': False},
                    {'text': 'Choice 4', 'is_correct': False},
                ],
            }
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        question = Question.objects.get(pk=response.data['id']).translated
        data = data['translated']
        self.assertEqual(question.text, data['text'])
        self.assertEqual(question.language, data['language'])
        self.assertEqual(question.publisher, self.user)
        self.assertEqual(question.technology, self.technology)
        self.assertEqual(question.duration, question.original.duration)

    def test_create_with_insufficient_choices(self):
        data = {
            'text': 'New Question',
            'technology': self.technology.pk,
            'language': Language.ENGLISH,
            'difficulty': Question.Difficulty.EASY,
            'explanation': 'Explanation for new question',
            'choices': [
                {'text': 'Choice 1', 'is_correct': True},
            ],
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('choices', response.data)

    def test_create_question_with_translation_insufficient_choice_data(self):
        data = {
            'text': 'New Question',
            'technology': self.technology.pk,
            'language': Language.ENGLISH,
            'evaluation': self.evaluation.pk,
            'difficulty': Question.Difficulty.EASY,
            'duration': 30,
            'explanation': 'Explanation for new question',
            'choices': [
                {'text': 'Choice 1', 'is_correct': True},
                {'text': 'Choice 2', 'is_correct': False},
                {'text': 'Choice 3', 'is_correct': False},
                {'text': 'Choice 4', 'is_correct': False},
            ],
            'translated': {
                'text': 'New Question',
                'language': Language.FRENCH,
                'explanation': 'Explanation for new question',
                'choices': [
                    {'text': 'Choice 1'},
                    {'text': 'Choice 2'},
                    {'text': 'Choice 3'},
                    {'text': 'Choice 4'},
                ],
            }
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        question = Question.objects.get(pk=response.data['id']).translated
        self.assertEqual(question.text, data['text'])
        for i, (choice, trans_choice) in enumerate(zip(question.original.choices.all(), question.choices.all())):
            self.assertEqual(choice.is_correct, trans_choice.is_correct)
