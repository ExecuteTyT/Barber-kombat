# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## О проекте

MAKON (Barber Kombat) — система управления и мотивации персонала для сети барбершопов. Telegram Mini App + FastAPI бэкенд. Все данные синхронизируются из YClients.

Ключевые модули: Barber Kombat (геймификация), ПВР (премирование), отчётность, планирование, отзывы.

## Команды разработки

### Backend
```bash
cd backend
# Запуск сервера
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Тесты
python -m pytest tests/ -v
# Один тест
python -m pytest tests/test_whatsapp.py -v
# Миграции
alembic upgrade head
alembic revision --autogenerate -m "description"
# Демо-данные
PYTHONIOENCODING=utf-8 python -m app.cli seed-demo
# Type check (нет mypy, проверяется вручную)
```

### Frontend
```bash
cd frontend
npm run dev          # Dev server (порт 3000)
npm run build        # Сборка (tsc + vite build)
npx tsc --noEmit     # Проверка типов без сборки
npm run lint         # ESLint
```

### Dev-авторизация
```
POST http://localhost:8000/api/v1/auth/dev-login
Body: {"telegram_id": 900000001}
```
Работает только при `APP_ENV=development`. Возвращает JWT-токен.

## Архитектура

### Потоки данных
```
YClients API → SyncService → PostgreSQL → RatingEngine → daily_ratings
                                        → ReportService → reports (cache)
                                        → PlanService → plan tracking
Redis Pub/Sub → WebSocket → Frontend (real-time updates)
Celery tasks → WhatsApp/Telegram (notifications)
```

### Backend: ключевые модули
- **`app/services/rating.py`** — `RatingEngine`: вычисляет ежедневные рейтинги барберов по 5 метрикам (выручка, средний чек, товары, допуслуги, отзывы). Нормализация, веса, ранжирование → `daily_ratings` таблица
- **`app/services/sync.py`** — `SyncService`: синхронизация визитов из YClients. Автопагинация (300 записей/страница)
- **`app/services/reports.py`** — `ReportService`: генерация отчётов (day-to-day, kombat, revenue). Кэширование в таблице `reports`
- **`app/integrations/yclients/client.py`** — HTTP-клиент для YClients API
- **`app/integrations/whatsapp/client.py`** — GreenAPI клиент для WhatsApp
- **`app/integrations/telegram/bot.py`** — Telegram-бот + форматирование сообщений

### Frontend: экраны по ролям
- **`screens/barber/`** — KombatScreen (рейтинг), ProgressScreen (ПВР), HistoryScreen (история)
- **`screens/chef/`** — BranchScreen (филиал), ChefKombatScreen, ChefPVRScreen, ChefAnalyticsScreen
- **`screens/owner/`** — DashboardScreen, ReportsScreen, CompetitionsScreen, SettingsScreen
- **`stores/`** — Zustand: barberStore, chefStore, ownerStore, pvrStore

### Ключевые бизнес-концепции
- **CS (средний чек)** — коэффициент `services_revenue / haircut_price`, отображается как ×2.56
- **ПВР** — прогрессивное вознаграждение: пороги выручки с бонусами за их достижение
- **Мультитенантность** — `organization_id` в каждой таблице, фильтрация на уровне сервисов

### API
- Все роутеры под `/api/v1/`
- WebSocket: `ws://host/ws?token=JWT`
- Health check: `GET /api/health`
- Swagger docs: `GET /api/docs` (только в development)

## Правила кодирования

### Python
- Type hints, async/await, Pydantic v2, SQLAlchemy 2.0 (select-стиль)
- Логирование: structlog. Сервисы: DI через FastAPI Depends
- Alembic миграция при каждом изменении модели

### TypeScript
- Строгая типизация (no `any`), Zustand для стейта, Tailwind для стилей
- Telegram-тема: цвета через CSS-переменные из themeParams
- Один файл = один компонент

### Общие
- Конфиг через env-переменные (см. `app/config.py` — все поля Settings)
- organization_id в каждой таблице (мультитенантность)
- Комментарии на английском, UI на русском
- Git: conventional commits (feat:, fix:, refactor:, docs:)

## Известные особенности

- **StrEnum + SQLAlchemy на Python 3.14**: нужен явный `values_callable` в `Enum()`, иначе записывается `.name` вместо `.value`
- **YClients client.id**: у некоторых клиентов нет `id` — поле `YClientRecordClient.id` имеет дефолт `0`
- **YClients Staff API**: НЕ возвращает цены стрижек. Цены — через Services API
- **Деплой**: фронт на Vercel (auto-deploy из main), бэкенд на отдельном сервере

## Документация
- `docs/modules/` — спецификации каждого модуля
- `docs/architecture/` — архитектура, модель данных, синхронизация
- `docs/api/endpoints.md` — REST API спецификация
- `plans/development-plan.md` — план разработки
