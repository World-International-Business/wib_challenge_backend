import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wib_challenge.settings.development')
django.setup()

from education.models import School, SchoolStaff, AcademicClass, Subject, Student
from django.contrib.auth import get_user_model

User = get_user_model()

print("Test de connexion a la base de donnees...")
print(f"Ecoles: {School.objects.count()}")
print(f"Classes: {AcademicClass.objects.count()}")
print(f"Matieres: {Subject.objects.count()}")
print(f"Enseignants: {SchoolStaff.objects.count()}")
print(f"Eleves: {Student.objects.count()}")