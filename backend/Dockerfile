# syntax=docker/dockerfile:1
#
# Print Service backend — Django 5 + DRF served by gunicorn.
#
#   docker build -t printservice-backend ./backend
#
# Runtime state lives on volumes:
#   /app/data   -> SQLite database (when DB_ENGINE=sqlite)
#   /app/media  -> uploaded order files
# Configure everything through environment variables (see ../.env.example).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so source edits don't bust the layer cache.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent runtime directories + an unprivileged user that owns them (named
# volumes inherit this ownership, so no root-owned bind-mount surprises).
RUN mkdir -p /app/data /app/media /app/staticfiles \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app

COPY --chmod=0755 entrypoint.sh /usr/local/bin/entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health/', timeout=4)"

ENTRYPOINT ["entrypoint.sh"]