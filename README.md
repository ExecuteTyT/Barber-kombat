# Barber Kombat

Automated management and gamification system for barbershop chains.
Telegram Mini App + FastAPI backend.

## Features

- **Barber Kombat** — daily rating competitions with prize funds
- **PVR** — cumulative monthly bonuses with threshold bell notifications
- **Reports** — automated daily, day-to-day, and monthly reports via Telegram
- **Plans** — revenue planning and progress tracking per branch
- **Reviews** — client review collection and processing
- **Real-time updates** — WebSocket live rating board
- **Multi-tenant** — supports multiple organizations and branches

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.0, Celery |
| Database | PostgreSQL 16, Redis 7 |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Telegram | @telegram-apps/sdk, python-telegram-bot |
| Infra | Docker, Nginx, Alembic |

---

## Quick Start (Development)

### Prerequisites

- Docker + Docker Compose
- Python 3.12+
- Node.js 20+
- Telegram Bot Token (from @BotFather)
- YClients API key + Bearer Token

### 1. Start Infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env
# Edit .env — fill in tokens and secrets

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://localhost:3000` with API proxy to `localhost:8000`.

### 4. Celery Workers

```bash
cd backend

# Worker (in one terminal)
celery -A app.tasks worker --loglevel=info --concurrency=2

# Beat scheduler (in another terminal)
celery -A app.tasks beat --loglevel=info
```

### 5. Seed Data

```bash
cd backend

python -m app.cli seed \
    --org-name "My Barbershop" \
    --org-slug "my-barbershop" \
    --owner-telegram-id 123456789 \
    --owner-name "Ivan" \
    --branch-name "Main Branch" \
    --branch-address "123 Main St" \
    --yclients-company-id 555
```

Creates: organization, branch, owner user, rating config, PVR config.

### 6. Initial YClients Sync

```bash
python -m app.cli sync-initial --org-id <ORG_UUID>
```

---

## Local Demo Testing (No Telegram / No YClients)

Step-by-step guide to test the full UI locally in a browser, without Telegram or YClients.

### 1. Start PostgreSQL + Redis

```bash
docker compose -f docker-compose.dev.yml up -d db redis
```

Wait until healthy:
```bash
docker compose -f docker-compose.dev.yml ps
```

### 2. Setup Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in the **project root** (or copy `.env.example`):
```bash
cp ../.env.example .env
```

Minimum `.env` for demo:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/barber_kombat
REDIS_URL=redis://localhost:6379/0
APP_ENV=development
JWT_SECRET=demo-secret-key-at-least-32-characters-long
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 3. Run Migrations

```bash
cd backend
alembic upgrade head
```

### 4. Seed Demo Data

```bash
python -m app.cli seed-demo
```

This creates:
- Organization "Demo Barbershop" with 2 branches
- 5 barbers, 1 chef, 1 owner, 1 admin
- 7 days of daily ratings, visits, PVR records
- Plans, reviews, reports, notification configs

The output shows all users with their `telegram_id` values.

### 5. Start Backend

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/api/docs

### 6. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### 7. Open in Browser

Go to **http://localhost:3000**

Since you're not inside Telegram, a **Dev Login Screen** appears with a list of all demo users. Click any user to log in as that role:

| Role | What you see |
|------|--------------|
| **Барбер** | Kombat rating board, personal progress, history |
| **Шеф** | Branch overview, PVR table, kombat board |
| **Владелец** | Dashboard, reports, competitions, settings |
| **Администратор** | Metrics, tasks, admin history |

A **Dev Toolbar** at the bottom shows the current user. Click "Сменить" to switch to another user.

### 8. (Optional) Start Celery

Only needed if you want to test background tasks (reports, notifications):

```bash
# Terminal 1
cd backend
celery -A app.tasks worker --loglevel=info --concurrency=2

# Terminal 2
cd backend
celery -A app.tasks beat --loglevel=info
```

### Dev Auth API (for Postman/curl)

```bash
# List available demo users
curl http://localhost:8000/api/v1/auth/dev-users

# Login as a specific user
curl -X POST http://localhost:8000/api/v1/auth/dev-login \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 900000001}'

# Login by role (first user with this role)
curl -X POST http://localhost:8000/api/v1/auth/dev-login \
  -H "Content-Type: application/json" \
  -d '{"role": "owner"}'
```

> **Note:** Dev endpoints only work when `APP_ENV=development`.

---

## Production Deployment

### 1. Configure

```bash
cp .env.production .env
# Edit .env with real credentials

mkdir -p ssl
# Copy SSL certificates: ssl/fullchain.pem, ssl/privkey.pem
```

### 2. Deploy

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

This builds images, runs migrations, starts all services, verifies health.

### 3. First-Time Seed

```bash
docker compose exec backend python -m app.cli seed \
    --org-name "Barbershop" \
    --org-slug "barbershop" \
    --owner-telegram-id 123456789 \
    --owner-name "Ivan" \
    --yclients-company-id 555

docker compose exec backend python -m app.cli sync-initial \
    --org-id <ORG_UUID>
```

### 4. Backups

Automatic daily backups at 03:00 via `db-backup` container. Manual:

```bash
./scripts/backup.sh                                    # Create backup
./scripts/backup.sh --restore backups/file.dump        # Restore
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m app.cli seed` | Create org, branch, owner, configs |
| `python -m app.cli seed-demo` | Populate full demo data for local testing |
| `python -m app.cli sync-initial --org-id UUID` | Initial YClients sync |
| `python -m app.cli monthly-reset --month 2026-01` | Finalize a month manually |
| `python -m app.cli monthly-reset --month 2026-01 --org-id UUID` | Reset single org |

---

## Celery Beat Schedule

| Task | Schedule | Description |
|------|----------|-------------|
| `poll_yclients` | Every 10 min | Incremental YClients sync |
| `full_sync_yclients` | Daily 04:00 | Full daily reconciliation |
| `generate_daily_reports` | Daily 22:30 | Generate daily reports |
| `deliver_daily_notifications` | Daily 22:35 | Send reports to Telegram |
| `generate_day_to_day` | Daily 11:00 | Day-to-day comparison |
| `deliver_day_to_day_notifications` | Daily 11:05 | Send comparison reports |
| `generate_monthly_reports` | 28th 23:00 | Monthly summary |
| `deliver_monthly_notifications` | 28th 23:10 | Send monthly reports |
| `monthly_reset` | 1st 00:05 | Finalize month, create new records |
| `check_unprocessed_reviews` | Every 30 min | Process pending reviews |

Times are Moscow timezone (Europe/Moscow).

---

## Testing

```bash
cd backend

python -m pytest                                          # All tests
python -m pytest --cov=app --cov-report=html              # With coverage
python -m pytest tests/test_e2e_integration.py -v         # E2E tests only
python -m pytest tests/test_e2e_integration.py::TestWebSocketConcurrency -v
```

---

## Architecture

```
Client (Telegram Mini App)
    |
    v
Nginx (SSL, rate limiting, WebSocket upgrade)
    |
    +-- /api/* --> FastAPI (REST API)
    +-- /ws    --> FastAPI (WebSocket, JWT auth)
    +-- /*     --> React SPA (static)

FastAPI <--> PostgreSQL (data, Alembic migrations)
    |
    +--> Redis (cache, pub/sub, Celery broker)
    +--> Celery Worker (sync, reports, notifications)
    +--> Celery Beat (scheduler)
    +--> Telegram Bot API (push notifications)
    +--> YClients API (data source)
```

## Health Check

```
GET /api/health
```

```json
{"status": "ok", "db": "connected", "redis": "connected"}
```

---

## Documentation

- `CLAUDE.md` — project context, stack, coding rules
- `docs/architecture/` — architecture, data model, sync
- `docs/modules/` — module specifications
- `docs/api/` — REST API specification
- `docs/frontend/` — screens, Telegram bot
- `plans/development-plan.md` — step-by-step development plan

## License

Private. All rights reserved.
