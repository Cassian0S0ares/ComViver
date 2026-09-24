FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=comviver.settings.prod

# Bibliotecas nativas do WeasyPrint (recibos em PDF).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ requirements/
RUN pip install -r requirements/prod.txt

COPY . .

# collectstatic não acessa o banco, mas as settings exigem as variáveis.
RUN SECRET_KEY=build-only ALLOWED_HOSTS=localhost \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    python manage.py collectstatic --noinput

RUN useradd --create-home comviver && chown -R comviver /app
USER comviver

CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn comviver.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
