FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=wib_challenge.settings.production

WORKDIR /app

COPY requirements.txt .
RUN echo >> requirements.txt && echo 'ipython' >> requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser --disabled-password --gecos "" django
RUN chown -R django:django /app
USER django

COPY --chown=django:django . .

RUN python manage.py collectstatic --noinput && mkdir -p /app/media \
    && chown -R django:django /app/media && chmod +x ./entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "--fail", "http://localhost:8000/health" ]

ENTRYPOINT [ "sh", "./entrypoint.sh" ]
