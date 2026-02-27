# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Barber Kombat — Telegram Mini App for barbershop staff management and gamification. Features daily barber competitions (Kombat), premium bonuses (PVR), automated reporting, revenue planning, and customer review processing. Built as a multi-tenant system syncing with YClients CRM.

## Development Commands

### Backend (Python 3.12 + FastAPI)

```bash
# Start infrastructure (PostgreSQL + Redis + Celery)
docker compose -f docker-compose.dev.yml up -d

# Install dependencies
cd backend && pip install -r requirements.txt

# Run database migrations
cd backend && alembic upgrade head

# Seed demo data (creates org, branch, 5 barbers, 7 days of history)
cd backend && python -m app.cli seed-demo

# Start API server (dev)
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
cd backend && pytest

# Run single test file
cd backend && pytest tests/test_rating.py

# Run specific test
cd backend && pytest tests/test_rating.py::test_function_name -v

# Lint
cd backend && ruff check app/ tests/
cd backend && ruff format --check app/ tests/
```

### Frontend (React 18 + TypeScript + Vite)

```bash
cd frontend && npm install
cd frontend && npm run dev          # Dev server on port 3000
cd frontend && npm run build        # Production build
cd frontend && npm run lint         # ESLint
cd frontend && npm run preview      # Preview production build
```

### Docker (full stack production)

```bash
# Production deployment (requires .env and SSL certs in ssl/)
./scripts/deploy.sh start

# View logs
docker compose logs -f backend
```

## Architecture

### Backend Data Flow

**Request → Router → Service → Database/Cache**

- **Routers** (`backend/app/api/`): 8 FastAPI routers under `/api/v1` — auth, config, kombat, plans, pvr, reports, reviews, webhooks. Handle HTTP validation, auth checks, response formatting.
- **Services** (`backend/app/services/`): Business logic classes — RatingEngine (kombat scoring), SyncService (YClients sync), PVR/Reports/Plans/Reviews/Config services. Services use async SQLAlchemy sessions via dependency injection.
- **Models** (`backend/app/models/`): 14 SQLAlchemy models. Every model has `organization_id` FK for multi-tenancy.
- **Schemas** (`backend/app/schemas/`): Pydantic v2 request/response models for all endpoints.

### Real-Time Updates

Redis pub/sub → WebSocket broadcast (scoped by organization_id):
- Backend services publish events to Redis channels
- `main.py` lifespan runs a Redis listener that forwards to `ws_manager`
- `ws_manager` (`backend/app/websocket/manager.py`) broadcasts to all WebSocket clients in the same org
- Frontend `useWebSocket` hook handles connection, reconnection, and message routing

### Background Tasks (Celery)

Configured in `backend/app/tasks/celery_app.py` with 11 beat schedules:
- **Sync**: YClients polling every 10min, full reconciliation daily at 04:00
- **Reports**: Daily revenue at 22:30, day-to-day at 11:00, monthly on 28th
- **Reviews**: Check unprocessed every 30min
- **Monthly reset**: 1st of month at 00:05 (finalize scores, create new PVR records)

All times in Europe/Moscow timezone.

### Authentication

1. Telegram Mini App sends `initData` → `POST /auth/telegram` validates HMAC-SHA256 signature → returns JWT
2. JWT contains `user_id`, `organization_id`, `role` (24hr TTL)
3. `get_current_user()` dependency extracts JWT from Bearer header
4. `require_role()` dependency enforces RBAC (5 roles: OWNER, MANAGER, CHEF, BARBER, ADMIN)
5. **Dev mode**: `POST /auth/dev-login` bypasses Telegram auth when `APP_ENV != production`

### Frontend Architecture

- **Routing**: Role-based layouts — `/barber/*`, `/chef/*`, `/owner/*`, `/admin/*`
- **State**: 6 Zustand stores (auth, kombat, pvr, owner, reviews, admin)
- **API client** (`frontend/src/api/client.ts`): Axios with auto Bearer token injection and 401 logout
- **Dev mode**: When no Telegram `initData` detected, shows DevLoginScreen + DevToolbar for user switching
- Vite dev server proxies `/api` and `/ws` to `localhost:8000`

### Kombat Scoring Algorithm

1. SyncService pulls visits from YClients → stores as Visit records
2. RatingEngine collects daily metrics per barber: revenue, CS value (client satisfaction), products count, extras count, reviews avg
3. Each metric normalized to 0-100 using configurable min/max thresholds
4. Weighted sum calculated using `rating_config` weights (configurable per org)
5. Barbers ranked; prizes distributed from daily prize fund by percentage tiers
6. Results cached in Redis (24hr TTL) and broadcast via WebSocket

### Multi-Tenancy

Every database table has `organization_id` FK. WebSocket broadcasts are org-scoped. All queries filter by org. JWT carries org context.

## Key Conventions

### Python (Backend)
- Async/await for all I/O; SQLAlchemy 2.0 style (`select()`, not `query()`)
- Pydantic v2 for all input/output schemas
- Services are classes with dependency injection via FastAPI `Depends`
- Logging via `structlog`; all SQL through ORM (no raw SQL)
- Create Alembic migrations for every model change (current: single migration `0001`)
- Type hints everywhere; docstrings on public methods
- Currency stored as integers (kopeks) to avoid float precision issues

### TypeScript (Frontend)
- Strict typing, no `any`
- Functional components; one component per file
- Zustand for global state; custom hooks for business logic (`useKombatRating`, `usePVR`)
- Tailwind CSS only (no inline CSS)
- Telegram theme adaptation via `Telegram.WebApp.themeParams`

### General
- All config via environment variables (never hardcode IDs)
- Comments in English; UI text in Russian
- Git: conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`)
- Read the relevant `docs/modules/*.md` file before working on any module
- Follow `plans/development-plan.md` for implementation sequencing

## External Integrations

- **YClients API** (https://api.yclients.com): CRM sync for visits, staff, services, clients. Rate-limited client with retry logic in `backend/app/integrations/yclients/client.py`
- **Telegram Bot API**: Push notifications via python-telegram-bot. Auth via initData HMAC validation.
- **WhatsApp Business** (optional): Review request sending via Wazzup/GreenAPI. Fallback to Telegram.

## Out of Scope (MVP)
Bank integration, Admin Kombat, marketing module, Power BI dashboards, native mobile app.
