FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .
COPY backend/scripts/entrypoint.sh /entrypoint.sh

RUN mkdir -p /tmp/autodev_repos \
    && chmod +x /entrypoint.sh

RUN useradd -m -u 1001 autodev && chown -R autodev:autodev /app /tmp/autodev_repos
USER autodev

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
