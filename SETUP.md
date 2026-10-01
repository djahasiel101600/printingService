# Print Service — Setup & Configuration Guide

This guide covers everything needed to run the full application locally, including optional integrations with Epson Connect and PayMongo.

> **Deploying with Docker?** See [DOCKER.md](DOCKER.md) for the containerized
> setup published through the shared `jdp-network` + Cloudflare tunnel
> (`docker compose up -d --build`).

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start (Mock Mode)](#3-quick-start-mock-mode)
4. [Backend Configuration](#4-backend-configuration)
5. [Frontend Configuration](#5-frontend-configuration)
6. [Database Setup & Seeding](#6-database-setup--seeding)
7. [Running the Application](#7-running-the-application)
8. [Epson Connect API Setup (Optional)](#8-epson-connect-api-setup-optional)
9. [PayMongo Integration Setup (Optional)](#9-paymongo-integration-setup-optional)
10. [Email Notifications (Optional)](#10-email-notifications-optional)
11. [Production Deployment Notes](#11-production-deployment-notes)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Architecture Overview

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | Django 5.2 + Django REST Framework | API, business logic, database |
| Frontend | React 18 + Vite + TypeScript | User interface |
| UI Components | Shadcn UI + Tailwind CSS | Styled components |
| Auth | JWT (simplejwt) | User authentication |
| Database | SQLite (dev) / PostgreSQL (prod) | Data storage |
| External | Epson Connect API v2 | Print job submission |
| External | PayMongo API | QR Ph payments |

**Project Structure:**
```
printingService/
├── backend/               # Django REST API
│   ├── apps/
│   │   ├── accounts/      # User management & auth
│   │   ├── orders/        # Order workflow & files
│   │   ├── payments/      # PayMongo integration
│   │   ├── pricing/       # Quotation engine
│   │   └── printing/      # Epson Connect integration
│   ├── print_service/     # Project settings
│   ├── requirements.txt
│   └── .env.example
├── frontend/              # React + Vite
│   ├── src/
│   │   ├── components/    # UI components (shadcn)
│   │   ├── pages/         # Route pages
│   │   └── lib/           # API client, types, utils
│   └── package.json
└── openapi.spec           # Epson Connect API reference
```

---

## 2. Prerequisites

Ensure the following are installed:

| Tool | Minimum Version | Download |
|------|----------------|----------|
| Python | 3.11+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| npm | 9+ | Included with Node.js |
| Git | Any | https://git-scm.com |

Verify installations:
```bash
python --version    # Python 3.11+
node --version      # v18+
npm --version       # 9+
```

---

## 3. Quick Start (Mock Mode)

The application runs with **mock integrations** by default — no external API keys required.

### Step 1: Clone and setup backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run migrations
python manage.py migrate
```

### Step 2: Setup frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env
```

### Step 3: Seed demo data

```bash
cd backend
python manage.py seed_demo
```

This creates:
- Default pricing rules
- Admin account: `admin@print.local` / `admin1234`
- Demo client: `client@example.com` / `client1234`

### Step 4: Run both servers

```bash
# Terminal 1 — Backend
cd backend
python manage.py runserver

# Terminal 2 — Frontend
cd frontend
npm run dev
```

### Step 5: Access the app

- Frontend: http://localhost:5173
- Backend API: http://127.0.0.1:8000/api
- Django Admin: http://127.0.0.1:8000/admin

---

## 4. Backend Configuration

Create `backend/.env` from `.env.example`:

```bash
cp backend/.env.example backend/.env
```

### Required Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-insecure-secret-key-change-me` | Django secret key (change in production!) |
| `DEBUG` | `True` | Set `False` in production |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Frontend origins for CORS |

### Business Rules

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_PARTIAL_PERCENT` | `50` | Minimum down payment percentage |
| `DUPLEX_DISCOUNT_FACTOR` | `0.90` | Price multiplier for double-sided printing |

### Generating a Secret Key

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 5. Frontend Configuration

Create `frontend/.env` from `.env.example`:

```bash
cp frontend/.env.example frontend/.env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://127.0.0.1:8000/api` | Backend API base URL |

> **Important:** No trailing slash in the URL.

---

## 6. Database Setup & Seeding

### Migrations

```bash
cd backend
python manage.py migrate
```

This creates tables for:
- Users & authentication
- Pricing rules
- Orders, files, specifications
- Payments
- Print jobs
- Admin logs

### Seed Demo Data

```bash
python manage.py seed_demo
```

**What it creates:**

**Pricing Rules** (price per printed side in centavos):

| Paper | Type | Color | Quality | Price (PHP) |
|-------|------|-------|---------|-------------|
| A4 | Plain | Mono | Normal | ₱3.00 |
| A4 | Plain | Mono | Draft | ₱2.50 |
| A4 | Plain | Mono | High | ₱5.00 |
| A4 | Plain | Color | Normal | ₱10.00 |
| A4 | Plain | Color | Draft | ₱8.00 |
| A4 | Plain | Color | High | ₱15.00 |
| Letter | Plain | Mono | Normal | ₱3.00 |
| Letter | Plain | Color | Normal | ₱10.00 |
| A3 | Plain | Mono | Normal | ₱6.00 |
| A3 | Plain | Color | Normal | ₱20.00 |
| Any | Photo | Color | High | ₱35.00 |

**User Accounts:**

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@print.local` | `admin1234` |
| Client | `client@example.com` | `client1234` |

### Customize Seed Data

Override defaults via environment variables:

```bash
SEED_ADMIN_EMAIL=my@email.com SEED_ADMIN_PASSWORD=secure123 python manage.py seed_demo
```

| Variable | Default | Description |
|----------|---------|-------------|
| `SEED_ADMIN_EMAIL` | `admin@print.local` | Admin email |
| `SEED_ADMIN_PASSWORD` | `admin1234` | Admin password |
| `SEED_CLIENT_EMAIL` | `client@example.com` | Demo client email |
| `SEED_CLIENT_PASSWORD` | `client1234` | Demo client password |

---

## 7. Running the Application

### Development Mode

**Terminal 1 — Backend:**
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python manage.py runserver
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

### Useful Management Commands

```bash
# Sync print job statuses from Epson
python manage.py sync_print_jobs

# Create a superuser (alternative to seed_demo)
python manage.py createsuperuser

# Run tests
python manage.py test
```

### Build for Production

```bash
cd frontend
npm run build
```

Output goes to `frontend/dist/`.

---

## 8. Epson Connect API Setup (Optional)

To use a real Epson printer, disable mock mode and configure credentials.

### Step 1: Register for Epson Developer Access

1. Visit [Epson Developer Portal](https://developer.epson.com/)
2. Create an application to get API credentials
3. Note your `Client ID` and `Client Secret`

### Step 2: Get Printer Authorization

The printer must be registered to an Epson Connect account. You'll need:

- Printer registered to an Epson account
- Email/password used for printer registration

### Step 3: Configure Environment

Update `backend/.env`:

```env
# Disable mock mode
EPSON_MOCK_MODE=False

# API endpoints (defaults shown)
EPSON_API_BASE=https://api.epsonconnect.com/api/2
EPSON_UPLOAD_BASE=https://upload.epsonconnect.com
EPSON_AUTH_BASE=https://auth.epsonconnect.com

# Your app credentials
EPSON_API_KEY=your-api-key-here
EPSON_CLIENT_ID=your-client-id
EPSON_CLIENT_SECRET=your-client-secret

# Device authorization method
EPSON_DEVICE_GRANT=password
EPSON_DEVICE_EMAIL=printer@email.com
EPSON_DEVICE_PASSWORD=printer-password
EPSON_PRINTER_NAME=Shop Printer
```

### Device Grant Types

| Method | Required Variables | Use Case |
|--------|-------------------|----------|
| `password` | `EPSON_DEVICE_EMAIL`, `EPSON_DEVICE_PASSWORD` | Direct printer credentials |
| `refresh_token` | `EPSON_DEVICE_REFRESH_TOKEN` | Reuse existing token |
| `authorization_code` | `EPSON_AUTH_CODE` | OAuth code flow |

### Important: Authorization Code Flow

Epson Connect API v2 does NOT support the `password` grant type for device tokens. You must use the **authorization code flow**:

1. Generate the authorization URL:
   ```
   GET /api/admin/epson/auth-url/
   ```
2. Open the URL in a browser and log in with your Epson account
3. Epson redirects back with a `code` parameter
4. Exchange the code for tokens:
   ```
   POST /api/admin/epson/exchange-code/
   Body: { "code": "your-auth-code" }
   ```
5. Save the `refresh_token` to your `.env` as `EPSON_DEVICE_REFRESH_TOKEN`

### Mock Mode Behavior

When `EPSON_MOCK_MODE=True` (default):
- Capabilities return a realistic set of paper sizes/types
- Print jobs are simulated (no actual printing)
- Useful for development and testing

---

## 9. PayMongo Integration Setup (Optional)

To accept real QR Ph payments, disable mock mode and add PayMongo credentials.

### Step 1: Create PayMongo Account

1. Sign up at [PayMongo](https://www.paymongo.com/)
2. Complete verification
3. Get API keys from the dashboard

### Step 2: Configure Environment

Update `backend/.env`:

```env
# Disable mock mode
PAYMONGO_MOCK_MODE=False

# Your PayMongo secret key (starts with sk_live_ or sk_test_)
PAYMONGO_SECRET_KEY=sk_live_your_secret_key

# Webhook secret (for payment confirmations)
PAYMONGO_WEBHOOK_SECRET=your-webhook-secret

# Frontend URL for redirect after payment
FRONTEND_URL=http://localhost:5173
```

### Step 3: Set Up Webhook (Production)

1. In PayMongo dashboard, create a webhook endpoint
2. URL: `https://yourdomain.com/api/payments/webhook/`
3. Select events: `payment.paid`, `payment.failed`
4. Copy the webhook secret to your environment

### Mock Mode Behavior

When `PAYMONGO_MOCK_MODE=True` (default):
- QR codes are generated as placeholders
- Payments are simulated (no real charges)
- Webhooks can be triggered manually for testing

---

## 10. Email Notifications (Optional)

By default, emails are printed to the console (DEBUG mode). To send real emails:

```env
# Use SMTP backend
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend

# SMTP server settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Print Shop <your-email@gmail.com>
```

### Gmail Setup

1. Enable 2-Factor Authentication
2. Generate an [App Password](https://myaccount.google.com/apppasswords)
3. Use the app password in `EMAIL_HOST_PASSWORD`

---

## 11. Production Deployment Notes

### Security Checklist

- [ ] Change `SECRET_KEY` to a random value
- [ ] Set `DEBUG=False`
- [ ] Update `ALLOWED_HOSTS` with your domain
- [ ] Configure proper CORS origins
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set up proper email backend
- [ ] Enable HTTPS
- [ ] Set `EPSON_MOCK_MODE=False` (with real credentials)
- [ ] Set `PAYMONGO_MOCK_MODE=False` (with real credentials)

### Database (PostgreSQL)

```python
# settings.py override or environment-based config
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'printservice'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}
```

Add `psycopg2-binary` to `requirements.txt`.

### Static Files

```bash
python manage.py collectstatic
```

### Environment Variables for Production

```env
SECRET_KEY=your-random-50-char-string
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
FRONTEND_URL=https://yourdomain.com
```

---

## 12. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `CORS error` in browser | Check `CORS_ALLOWED_ORIGINS` includes your frontend URL |
| `401 Unauthorized` | Token expired or missing; log in again |
| `Cannot reach print server` | Backend is not running or `VITE_API_URL` is wrong |
| Files not uploading | Check `MEDIA_ROOT` directory exists and is writable |
| Email not sending | Verify SMTP settings or check console output |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `npm install` fails | Delete `node_modules` and `package-lock.json`, retry |

### Reset Database

```bash
cd backend
rm db.sqlite3
python manage.py migrate
python manage.py seed_demo
```

### Check API Health

```bash
# Test backend is running
curl http://127.0.0.1:8000/api/printing/capabilities/

# Test frontend
curl http://localhost:5173
```

---

## API Endpoints Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/accounts/register/` | Create account |
| POST | `/api/accounts/login/` | Get JWT tokens |
| POST | `/api/accounts/refresh/` | Refresh access token |
| GET | `/api/accounts/me/` | Get profile |

### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/orders/` | Create order (multipart) |
| GET | `/api/orders/mine/` | List my orders |
| GET | `/api/orders/{id}/` | Order detail |
| GET | `/api/track/{tracking_id}/` | Public tracking |

### Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/payments/checkout/` | Create QR Ph checkout |
| POST | `/api/payments/webhook/` | PayMongo webhook |

### Admin
---

## Admin Settings Panel

The application includes a built-in admin panel for managing API integrations:

- **URL**: `/admin/settings` (requires staff login)
- **Features**: 
  - Test Epson connection with live/mock mode toggle
  - Test PayMongo connection with live/mock mode toggle
  - Real-time test results with detailed error messages
  - Setup instructions for both services

### Epson OAuth Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/epson/auth-url/` | Get authorization URL |
| POST | `/api/admin/epson/exchange-code/` | Exchange code for tokens |
| POST | `/api/admin/epson/test-connection/` | Test connection |

### PayMongo Test Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/paymongo/test-connection/` | Test PayMongo connection |

### Test Connection Request Body

```json
{
  "mock_mode": false
}
```

### Test Connection Response

```json
{
  "mock_mode": false,
  "overall": "success|failed",
  "tests": {
    "application_token": { "status": "success|failed", "error": "..." },
    "device_token": { "status": "success|failed", "error": "..." },
    "device_info": { "status": "success", "data": {...} },
    "capabilities": { "status": "success", "paper_sizes": [...] }
  }
}
```
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/orders/` | List orders (filter by status) |
| GET | `/api/admin/orders/{id}/` | Order detail |
| POST | `/api/admin/orders/{id}/actions/{action}/` | Perform action |
| POST | `/api/admin/print-jobs/` | Sync printer statuses |

### Printing
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/printing/capabilities/` | Get printer capabilities |

---

## Support

For issues with external services:
- **Epson Connect:** https://developer.epson.com/
- **PayMongo:** https://developers.paymongo.com/

---

*Last updated: September 5, 2026*
