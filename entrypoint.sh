#!/bin/sh
set -e

python manage.py migrate --noinput

IMPORT_FIXTURE_PATH="${IMPORT_FIXTURE_PATH:-/app/database_exports/pending.json}"
if [ -f "$IMPORT_FIXTURE_PATH" ]; then
	echo "Importing database fixture from $IMPORT_FIXTURE_PATH"
	python manage.py loaddata "$IMPORT_FIXTURE_PATH"
	rm -f "$IMPORT_FIXTURE_PATH"
	echo "Database fixture imported and removed"
fi

python manage.py initialize
python manage.py create_default_questions
python manage.py collectstatic --noinput

exec gunicorn wib_challenge.wsgi:application --bind 0.0.0.0:8000 --workers 3 --threads 2
