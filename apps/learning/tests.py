from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Certificate, Content, Course, CourseEnrollment, ContentType, Module, Progress, Quiz, QuizChoice, QuizQuestion


class CandidateLearningSecurityTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='candidate@example.com', password='test-password')
        self.other_user = get_user_model().objects.create_user(email='other@example.com', password='test-password')
        self.course = Course.objects.create(
            title='Django sécurisé', description='Formation', level='beginner', is_free=True,
            price=0, is_published=True,
        )
        self.module = Module.objects.create(course=self.course, title='Introduction')
        self.content = Content.objects.create(
            module=self.module, title='Leçon', content_type=ContentType.MARKDOWN, content='Contenu privé',
        )

    def test_free_enrollment_is_idempotent(self):
        self.client.force_authenticate(self.user)
        url = f'/api/learnings/courses/{self.course.id}/enroll/'
        first = self.client.post(url)
        second = self.client.post(url)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(CourseEnrollment.objects.filter(user=self.user, course=self.course).count(), 1)

    def test_private_content_requires_active_enrollment(self):
        self.client.force_authenticate(self.user)
        url = f'/api/learnings/contents/{self.content.id}/'
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        CourseEnrollment.objects.create(user=self.user, course=self.course, status=CourseEnrollment.Status.ACTIVE)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_cannot_complete_content_without_enrollment(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(f'/api/learnings/contents/{self.content.id}/mark_completed/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Progress.objects.filter(user=self.user, content=self.content).exists())

    def test_quiz_does_not_expose_correct_choices(self):
        enrollment = CourseEnrollment.objects.create(user=self.user, course=self.course, status=CourseEnrollment.Status.ACTIVE)
        quiz = Quiz.objects.create(module=self.module, title='Quiz')
        question = QuizQuestion.objects.create(quiz=quiz, title='Question')
        QuizChoice.objects.create(question=question, text='Bonne réponse', is_correct=True)
        self.client.force_authenticate(self.user)
        response = self.client.get(f'/api/learnings/quizzes/{quiz.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('isCorrect', response.data['questions'][0]['choices'][0])
        self.assertEqual(enrollment.status, CourseEnrollment.Status.ACTIVE)

    def test_course_completion_progress(self):
        enrollment = CourseEnrollment.objects.create(user=self.user, course=self.course, status=CourseEnrollment.Status.ACTIVE)
        self.client.force_authenticate(self.user)
        self.client.post(f'/api/learnings/contents/{self.content.id}/mark_completed/')
        response = self.client.get(f'/api/learnings/courses/{self.course.id}/progress/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['percentage'] > 0)

    def test_certificate_not_issued_before_completion(self):
        CourseEnrollment.objects.create(user=self.user, course=self.course, status=CourseEnrollment.Status.ACTIVE)
        self.client.force_authenticate(self.user)
        response = self.client.get(f'/api/learnings/courses/{self.course.id}/certificate/eligibility/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_certificate_issued_after_completion(self):
        CourseEnrollment.objects.create(user=self.user, course=self.course, status=CourseEnrollment.Status.COMPLETED)
        self.client.force_authenticate(self.user)
        response = self.client.get(f'/api/learnings/courses/{self.course.id}/certificate/eligibility/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Certificate.objects.filter(user=self.user, course=self.course).exists())
