from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from core.models import Technology, Profession
from evaluations.models import Evaluation
from organizations.models import Organization, OrgEvaluation, ExperienceLevel
from questions.models import Question, Choice


class OrgEvaluationCreationTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User',
            role=User.Roles.ORG
        )

        self.organization = Organization.objects.create(
            name='Test Organization',
            account=self.user
        )

        self.python_tech = Technology.objects.create(name='Python')
        self.js_tech = Technology.objects.create(name='JavaScript')

        self.dev_profession = Profession.objects.create(title='Développeur Backend')

        self.python_eval = Evaluation.objects.create(
            title="Test Python Evaluation",
            description="Evaluation for testing Python skills",
            slug="test-python-evaluation",
            technology=self.python_tech
        )

        self.js_eval = Evaluation.objects.create(
            title="Test JavaScript Evaluation",
            description="Evaluation for testing JavaScript skills",
            slug="test-javascript-evaluation",
            technology=self.js_tech
        )

        self._create_test_questions(self.python_tech, self.python_eval)
        self._create_test_questions(self.js_tech, self.js_eval)

        self.client.force_authenticate(user=self.user)

        self.url = reverse('organizations:generate-evaluation')

    def _create_test_questions(self, technology, evaluation):
        """Crée des questions de test pour chaque niveau de difficulté"""
        for difficulty in [Question.Difficulty.EASY, Question.Difficulty.MEDIUM, Question.Difficulty.HARD]:
            for i in range(10):  # 10 questions par difficulté
                question = Question.objects.create(
                    text=f"Question {difficulty} {i} pour {technology.name}",
                    explanation=f"Explication pour la question {i}",
                    difficulty=difficulty,
                    technology=technology,
                    publisher=self.user,
                    status=Question.Status.PUBLISHED,
                    evaluation=evaluation
                )

                for j in range(4):
                    Choice.objects.create(
                        question=question,
                        text=f"Choix {j} pour question {i}",
                        is_correct=(j == 0)
                    )

    def test_automatic_evaluation_creation(self):
        """Teste la génération automatique d'une évaluation"""
        data = {
            'profession': self.dev_profession.title,
            'experience_level': ExperienceLevel.JUNIOR,
            'technologies': [self.python_tech.id, self.js_tech.id]
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(OrgEvaluation.objects.count(), 1)
        evaluation = OrgEvaluation.objects.first()

        self.assertEqual(evaluation.organization, self.organization)

        expected_title = f"Évaluation {self.dev_profession.title} - Junior"
        self.assertEqual(evaluation.title, expected_title)

        self.assertTrue(evaluation.questions.exists())

        python_questions = evaluation.questions.filter(technology=self.python_tech)
        js_questions = evaluation.questions.filter(technology=self.js_tech)

        self.assertTrue(python_questions.exists())
        self.assertTrue(js_questions.exists())

        # Junior: 60% facile, 30% intermédiaire, 10% difficile
        easy_count = evaluation.questions.filter(difficulty=Question.Difficulty.EASY).count()
        medium_count = evaluation.questions.filter(difficulty=Question.Difficulty.MEDIUM).count()
        hard_count = evaluation.questions.filter(difficulty=Question.Difficulty.HARD).count()

        total_count = easy_count + medium_count + hard_count

        # Vérifier que les proportions sont approximativement correctes 
        # (on ne peut pas garantir exactement 60%, 30%, 10% car cela dépend aussi 
        # du nombre de questions disponibles par technologie)
        self.assertGreater(easy_count, medium_count)  # Plus de faciles que d'intermédiaires
        self.assertGreater(medium_count, hard_count)  # Plus d'intermédiaires que de difficiles
