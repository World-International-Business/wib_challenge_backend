# json_processor.py

import json
from django.http import JsonResponse
from django.shortcuts import render
from django import forms
from django.conf import settings
from django.urls import path
from django.core.management import execute_from_command_line
from django.utils import timezone
import os

# Configure Django settings
settings.configure(
    DEBUG=True,
    SECRET_KEY='your-secret-key',
    ROOT_URLCONF=__name__,
    INSTALLED_APPS=[
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.admin',
    ],
)


# Create a simple Django server
if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'script')
    from django.core.management import execute_from_command_line

    execute_from_command_line(['manage.py', 'runserver', 'localhost:8000'])