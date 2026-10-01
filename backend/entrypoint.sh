#!/bin/sh
# Print Service backend entrypoint: wait for the database, apply migrations,
# collect static assets, then hand off to gunicorn.
set -e

cd /app

DB_ENGINE="${DB_ENGINE:-sqlite}"

if [ "$DB_ENGINE" = "postgres" ]; then
    echo "[entrypoint] waiting for postgres at ${DB_HOST:-printservice-db}:${DB_PORT:-5432} ..."
    python - <<'PY'
import os
import socket
import sys
import time

host = os.environ.get("DB_HOST", "printservice-db")
port = int(os.environ.get("DB_PORT", "5432"))
for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=3):
            print(f"[entrypoint] postgres is reachable at {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(2)
print(f"[entrypoint] ERROR: postgres at {host}:{port} never became reachable", file=sys.stderr)
sys.exit(1)
PY
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] applying migrations ..."
    python manage.py migrate --noinput
    echo "[entrypoint] collecting static files ..."
    python manage.py collectstatic --noinput
fi

if [ "${RUN_SEED_DEMO:-false}" = "true" ]; then
    echo "[entrypoint] seeding pricing rules / demo accounts ..."
    python manage.py seed_demo || true
fi

echo "[entrypoint] starting gunicorn on 0.0.0.0:${PORT:-8000} ..."
exec gunicorn print_service.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --worker-class gthread \
    --workers "${GUNICORN_WORKERS:-3}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --keep-alive "${GUNICORN_KEEPALIVE:-75}" \
    --access-logfile - \
    --error-logfile -