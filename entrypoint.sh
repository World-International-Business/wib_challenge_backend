#!/bin/sh
set -e

echo "Waiting for database..."
python manage.py wait_for_db

echo "Running migrations..."
python manage.py migrate accounts --noinput
python manage.py migrate --noinput

echo "Creating default admin..."
python manage.py create_default_admin

echo "Seeding core data..."
python manage.py seed_core --force
python manage.py seed_evaluations --force
python manage.py seed_courses --force

echo "Starting gunicorn..."
exec gunicorn wib_challenge.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120