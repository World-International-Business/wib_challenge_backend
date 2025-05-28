#!/usr/bin/env sh

git pull origin old_master
pip install -r requirements.txt
python manage.py collectstatic
python manage.py makemigrations
python manage.py migrate
