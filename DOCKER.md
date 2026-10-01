# Docker Deployment

This project ships as two containers published through the shared **cloudflared
tunnel** on the external `jdp-network`:

| Service | Image | Role | Network |
|---------|-------|------|---------|
| `printservice-frontend` | nginx + built SPA | Serves the React app and reverse-proxies `/api`, `/django-admin`, `/static`, `/media` to the backend. **This is the tunnel ingress target.** | `default`, `jdp-network` |
| `printservice-backend` | Django 5 + gunicorn | REST API, Django admin, uploaded media. | `default` |
| `printservice-db` | postgres:16-alpine | Optional database (profile `postgres`). | `default` |

```
                    ┌───────────────────────── jdp-network (external) ─────────────────────────┐
 Cloudflare ──────▶ │ cloudflared ──▶ printservice-frontend:80 ──▶ printservice-backend:8000   │
 tunnel             │                   (nginx: SPA + /api proxy)      (gunicorn: API)         │
                    └───────────────────────────────────────────────────────────────────────────┘
                                                        └──▶ printservice-db:5432 (optional)
```

---

## 1. Prerequisites

* Docker + Docker Compose v2
* The external network must exist (created once per host):
  ```bash
  docker network create jdp-network
  ```
* A cloudflared tunnel that is attached to `jdp-network`.

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and at minimum set:

* `SECRET_KEY` — generate one:
  ```bash
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
* `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`
  — use the public hostname wired to the tunnel (e.g. `print.jdp-homelab.space`).

> **Important:** cloudflared forwards the original public hostname as the `Host`
> header. It **must** appear in `ALLOWED_HOSTS`, otherwise Django rejects every
> request with `400 DisallowedHost`.

## 3. Point the tunnel at the frontend

In your `cloudflared` config, add an ingress rule for the hostname:

```yaml
tunnel: <your-tunnel-id>
credentials-file: /etc/cloudflared/<your-tunnel-id>.json

ingress:
  - hostname: print.jdp-homelab.space
    service: http://printservice-frontend:80   # service name = DNS name on jdp-network
  # ... your other projects ...
  - service: http_status:404
```

> The container name is `printservice-frontend`; on `jdp-network` it resolves to
> the frontend. `originRequest` defaults are fine — nginx already forwards the
> `X-Forwarded-*` headers Django needs.
## 4. Run

```bash
docker compose up -d --build
```

Then open `https://print.jdp-homelab.space`.

### First-time setup (create the admin)

A fresh deployment has **no admin user and no pricing rules**. Bootstrap it one
of two ways:

**1. Setup wizard (recommended).** Open `https://<your-host>/setup` and create
the shop administrator from the browser. It is a one-time page: the backend
returns `403` as soon as an admin exists, so it can never mint extra admins. The
account it creates is a full owner (API admin **and** `/django-admin/`). Pricing
rules still need seeding once:

```bash
docker compose exec printservice-backend python manage.py seed_demo
```

**2. Seed the demo data.** `seed_demo` creates the pricing rules *and* known
accounts — convenient for a demo, but **change these passwords before exposing
the site**, since they are public defaults:

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@print.local` | `admin1234` |
| Client | `client@example.com` | `client1234` |

```bash
docker compose exec printservice-backend python manage.py seed_demo
```

Set `RUN_SEED_DEMO=true` in `.env` to run it automatically on the next boot
(idempotent).

> The `seed_demo` admin has shop-admin rights in the app but is **not** a Django
> `is_staff` user, so it cannot open `/django-admin/`. The setup-wizard account
> can. Use `python manage.py createsuperuser` if you need an extra Django admin.

## 5. Useful commands

```bash
docker compose logs -f printservice-backend     # tail backend logs
docker compose logs -f printservice-frontend    # tail nginx logs
docker compose exec printservice-backend python manage.py migrate
docker compose exec printservice-backend python manage.py collectstatic --noinput
docker compose up -d --build                    # rebuild after code changes
```

Expose the app on the host for local testing (without the tunnel) by
uncommenting the `ports` mapping on `printservice-frontend` in
`docker-compose.yml` (`8080:80`), then browse `http://localhost:8080`.

---

## Database

**SQLite (default).** The database lives in the `printservice-data` volume
(`/app/data/db.sqlite3`) and uploaded files in `printservice-media`
(`/app/media`). Use this to keep existing local data. To import the existing
local SQLite database and uploads into the running containers:

```bash
docker compose cp backend/db.sqlite3 printservice-backend:/app/data/db.sqlite3
docker compose exec -T printservice-backend mkdir -p /app/media
docker compose cp backend/media/. printservice-backend:/app/media/
docker compose restart printservice-backend
```

**PostgreSQL.** To run on Postgres, set `DB_ENGINE=postgres` and a strong
`DB_PASSWORD` in `.env`, then start the bundled service:

```bash
docker compose --profile postgres up -d --build
docker compose exec printservice-backend python manage.py seed_demo
```

Migrate existing SQLite data if needed (`dumpdata` / `loaddata`):

```bash
docker compose exec printservice-backend python manage.py dumpdata \
  --exclude contenttypes --exclude auth.permission --indent 2 > backup.json
# switch .env to DB_ENGINE=postgres, restart, then:
docker compose exec -T printservice-backend python manage.py loaddata - < backup.json
```

---

## Health checks

| Container | Probe |
|-----------|-------|
| `printservice-backend` | `http://127.0.0.1:8000/api/health/` |
| `printservice-frontend` | `http://127.0.0.1/` |
| `printservice-db` | `pg_isready` |

```bash
docker compose ps        # STATES should show "healthy"
```

---

## Connecting the Epson printer

`EPSON_MOCK_MODE=True` simulates printing, so nothing else is needed to try the
app. To print for real:

1. Put your **application** credentials in `.env` (create the app at the
   [Epson developer portal](https://developer.epsonconnect.com/) → *My Apps*):

   ```env
   EPSON_MOCK_MODE=False
   EPSON_API_KEY=<api key>
   EPSON_CLIENT_ID=<client id>
   EPSON_CLIENT_SECRET=<client secret>
   ```

   then recreate the backend so the new env is picked up:

   ```bash
   docker compose up -d --force-recreate printservice-backend
   ```

2. Register the printer to Epson Connect with the Epson account that will own
   the jobs, then connect it from the app: **Admin → API Settings → Epson device
   authorization → Get authorization URL → Open Epson sign-in**.

   Before handing you a link, that button pre-flights the app credentials
   against Epson's token endpoint — if they are wrong or rotated you get an
   explanatory error instead of a browser dropped on Epson's `error400` page.

   Epson Connect API v2 has **no password grant** — the device token can only be
   minted through this authorization-code flow, so `EPSON_DEVICE_GRANT=password`
   always fails with `unsupported_grant_type`.

   The resulting refresh token is stored in the database and renews itself, so
   it does **not** need to be copied into `.env`. It lives in the
   `printservice-data` volume, so it survives rebuilds and restarts.

3. Confirm with **Test Epson Connection** — all four checks should pass.

> The `redirect_uri` is `$FRONTEND_URL/epson/callback` unless you set
> `EPSON_REDIRECT_URI`. It must **byte-for-byte match** the "Redirect URI" saved
> on the Epson app, otherwise Epson answers `invalid_client`.

---

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service definitions, `jdp-network`, volumes |
| `.env.example` | Template for all runtime configuration |
| `backend/Dockerfile` | Django + gunicorn image |
| `backend/entrypoint.sh` | Wait for DB → migrate → collectstatic → gunicorn |
| `backend/.dockerignore` | Keeps the build context lean |
| `frontend/Dockerfile` | Multi-stage Vite build → nginx |
| `frontend/nginx.conf` | SPA host + reverse proxy to the backend |
| `frontend/.dockerignore` | Keeps the build context lean |