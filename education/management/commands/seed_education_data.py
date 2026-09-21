from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import random

from education.models import School, SchoolStaff, AcademicClass, Subject, Student, TeacherQuestion, TeacherChoice

User = get_user_model()


class Command(BaseCommand):
    help = 'Peuple la base de donnees avec des donnees educatives initiales'

    def handle(self, *args, **options):
        self.stdout.write('Debut du peuplement...')
        
        try:
            self.create_schools()
            self.stdout.write('Etablissements OK')
            
            self.create_classes()
            self.stdout.write('Classes OK')
            
            self.create_subjects()
            self.stdout.write('Matieres OK')
            
            self.create_admins_and_teachers()
            self.stdout.write('Enseignants OK')
            
            self.create_students()
            self.stdout.write('Eleves OK')
            
            self.create_sample_questions()
            self.stdout.write('Questions OK')
            
            self.stdout.write(self.style.SUCCESS('Termine avec succes!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur: {str(e)}'))
            import traceback
            traceback.print_exc()

    def create_schools(self):
        schools_data = [
            {'name': 'Lycee General Leclerc', 'code': 'lycee-leclerc'},
            {'name': 'College Jean Tabi', 'code': 'college-jean-tabi'},
            {'name': 'Lycee Bilingue de Kribi', 'code': 'lycee-bilingue-kribi'},
        ]
        
        for data in schools_data:
            school, created = School.objects.get_or_create(
                code=data['code'],
                defaults={'name': data['name'], 'is_active': True}
            )
            if created:
                self.stdout.write(f'  - {school.name} cree')

    def create_classes(self):
        classes_data = [
            {'school_code': 'lycee-leclerc', 'name': '6eme A', 'level': '6eme', 'year': '2025-2026'},
            {'school_code': 'lycee-leclerc', 'name': 'Terminale D', 'level': 'Terminale', 'year': '2025-2026'},
            {'school_code': 'college-jean-tabi', 'name': 'Form 1A', 'level': 'Form 1', 'year': '2025-2026'},
            {'school_code': 'college-jean-tabi', 'name': 'Upper Sixth', 'level': 'Upper Sixth', 'year': '2025-2026'},
            {'school_code': 'lycee-bilingue-kribi', 'name': '6eme', 'level': '6eme', 'year': '2025-2026'},
        ]
        
        for data in classes_data:
            school = School.objects.get(code=data['school_code'])
            academic_class, created = AcademicClass.objects.get_or_create(
                school=school,
                name=data['name'],
                academic_year=data['year'],
                defaults={'level': data['level']}
            )
            if created:
                self.stdout.write(f'  - {academic_class.name} creee')

    def create_subjects(self):
        subjects_data = [
            {'school_code': 'lycee-leclerc', 'name': 'Mathematiques', 'code': 'MATH'},
            {'school_code': 'lycee-leclerc', 'name': 'Francais', 'code': 'FRA'},
            {'school_code': 'lycee-leclerc', 'name': 'Informatique', 'code': 'INFO'},
            {'school_code': 'college-jean-tabi', 'name': 'Mathematics', 'code': 'MATH'},
            {'school_code': 'college-jean-tabi', 'name': 'English', 'code': 'ENG'},
            {'school_code': 'college-jean-tabi', 'name': 'Computer Science', 'code': 'CS'},
            {'school_code': 'lycee-bilingue-kribi', 'name': 'Mathematiques', 'code': 'MATH'},
            {'school_code': 'lycee-bilingue-kribi', 'name': 'Informatique', 'code': 'INFO'},
        ]
        
        for data in subjects_data:
            school = School.objects.get(code=data['school_code'])
            subject, created = Subject.objects.get_or_create(
                school=school,
                name=data['name'],
                defaults={'code': data['code']}
            )
            if created:
                self.stdout.write(f'  - {subject.name} creee')

    def create_admins_and_teachers(self):
        teachers_data = [
            {
                'email': 'admin.leclerc@school.cm',
                'first_name': 'Jean',
                'last_name': 'Dupont',
                'password': 'Admin123!',
                'school_code': 'lycee-leclerc',
                'role': 'MANAGER'
            },
            {
                'email': 'prof.math@leclerc.cm',
                'first_name': 'Marie',
                'last_name': 'Martin',
                'password': 'Math123!',
                'school_code': 'lycee-leclerc',
                'role': 'TEACHER'
            },
            {
                'email': 'admin.tabi@school.cm',
                'first_name': 'John',
                'last_name': 'Smith',
                'password': 'Admin123!',
                'school_code': 'college-jean-tabi',
                'role': 'MANAGER'
            },
            {
                'email': 'prof.english@tabi.cm',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'password': 'English123!',
                'school_code': 'college-jean-tabi',
                'role': 'TEACHER'
            },
        ]
        
        for data in teachers_data:
            school = School.objects.get(code=data['school_code'])
            
            user, created = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password(data['password'])
                user.save()
                self.stdout.write(f'  - Utilisateur {user.email} cree')
            
            staff, created = SchoolStaff.objects.get_or_create(
                user=user,
                school=school,
                defaults={'role': data['role'], 'is_active': True}
            )
            
            if created:
                self.stdout.write(f'    - Profil enseignant cree')
            
            if data['role'] == 'TEACHER':
                classes = AcademicClass.objects.filter(school=school)[:2]
                staff.classes_taught.set(classes)

    def create_students(self):
        first_names = ['Jean', 'Marie', 'Pierre', 'Sophie', 'Luc', 'Emma']
        last_names = ['Martin', 'Bernard', 'Dubois', 'Thomas', 'Robert']
        
        classes = AcademicClass.objects.all()
        
        for academic_class in classes:
            for i in range(3):
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)
                student_number = f"{academic_class.name.replace(' ', '').upper()}{random.randint(1000, 9999)}"
                email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 99)}@student.{academic_class.school.code}.cm"
                
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'is_active': True,
                    }
                )
                
                if created:
                    user.set_password('Student123!')
                    user.save()
                
                student, created = Student.objects.get_or_create(
                    user=user,
                    defaults={
                        'school': academic_class.school,
                        'academic_class': academic_class,
                        'student_number': student_number,
                        'is_active': True
                    }
                )
                
                if created:
                    self.stdout.write(f'  - Eleve {user.email} cree')

    def create_sample_questions(self):
        teachers = SchoolStaff.objects.filter(role='TEACHER')
        
        sample_questions = [
            {
                'subject_name': 'Mathematiques',
                'title': 'Quelle est la solution de 2x + 5 = 13 ?',
                'question_type': 'UCQ',
                'points': 2,
                'choices': [
                    {'text': 'x = 4', 'is_correct': True},
                    {'text': 'x = 8', 'is_correct': False},
                    {'text': 'x = 3', 'is_correct': False},
                ]
            },
            {
                'subject_name': 'Informatique',
                'title': 'Quel langage est utilise pour le web ?',
                'question_type': 'MCQ',
                'points': 2,
                'choices': [
                    {'text': 'HTML', 'is_correct': True},
                    {'text': 'CSS', 'is_correct': True},
                    {'text': 'JavaScript', 'is_correct': True},
                    {'text': 'Python', 'is_correct': False},
                ]
            },
        ]
        
        for teacher in teachers:
            school = teacher.school
            subjects = Subject.objects.filter(school=school)
            
            for question_data in sample_questions:
                subject = subjects.filter(name__icontains=question_data['subject_name']).first()
                if not subject:
                    continue
                
                existing = TeacherQuestion.objects.filter(
                    created_by=teacher.user,
                    title=question_data['title'],
                    subject=subject
                ).first()
                
                if existing:
                    continue
                
                question = TeacherQuestion.objects.create(
                    subject=subject,
                    created_by=teacher.user,
                    title=question_data['title'],
                    question_type=question_data['question_type'],
                    points=question_data['points'],
                    is_active=True
                )
                
                for idx, choice_data in enumerate(question_data['choices']):
                    TeacherChoice.objects.create(
                        teacher_question=question,
                        text=choice_data['text'],
                        is_correct=choice_data['is_correct'],
                        position=idx + 1
                    )
                
                self.stdout.write(f'  - Question "{question.title}" creee')