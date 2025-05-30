#!/usr/bin/env sh

git pull origin old_master --no-edit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py makemigrations
python manage.py migrate
