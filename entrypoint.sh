python manage.py wait_for_db
python manage.py migrate
python manage.py create_default_admin
python manage.py seed_core --force
python manage.py seed_evaluations --force
python manage.py seed_courses --force
exec gunicorn wib_challenge.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120