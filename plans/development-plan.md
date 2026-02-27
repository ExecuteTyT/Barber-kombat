# План разработки Barber Kombat

## Как использовать этот план

Каждый шаг — отдельная задача для одной сессии Claude Code. Работай строго последовательно. Не переходи к следующему шагу, пока текущий не завершён и не проверен.

Перед каждым шагом читай указанные файлы из `docs/`.

---

## Фаза 1: Инфраструктура и каркас

### Шаг 1.1: Инициализация проекта

**Прочитать:** `CLAUDE.md`

**Задачи:**
1. Создать структуру директорий backend/ и frontend/ по схеме из CLAUDE.md
2. Инициализировать Python-проект: requirements.txt, pyproject.toml
3. Инициализировать React-проект: `npm create vite@latest` с React + TypeScript
4. Настроить Tailwind CSS
5. Создать docker-compose.dev.yml (PostgreSQL, Redis)
6. Создать .env.example
7. Создать .gitignore
8. Настроить ESLint + Prettier для frontend
9. Настроить ruff для backend

**Проверка:** `docker-compose -f docker-compose.dev.yml up -d` запускает PostgreSQL и Redis. `cd frontend && npm run dev` запускает фронтенд. Backend запускается: `cd backend && uvicorn app.main:app`.

---

### Шаг 1.2: Backend каркас

**Прочитать:** `docs/architecture/overview.md`

**Задачи:**
1. Создать `app/main.py` — FastAPI application с CORS, middleware
2. Создать `app/config.py` — Settings через pydantic-settings (из .env)
3. Создать `app/database.py` — async SQLAlchemy engine + sessionmaker
4. Создать `app/redis.py` — подключение к Redis через redis.asyncio
5. Настроить Alembic для миграций
6. Создать базовый health-check endpoint: `GET /api/health`
7. Настроить structlog для логирования

**Проверка:** `GET http://localhost:8000/api/health` возвращает `{"status": "ok", "db": "connected", "redis": "connected"}`.

---

### Шаг 1.3: Модели данных

**Прочитать:** `docs/architecture/data-model.md`

**Задачи:**
1. Создать все SQLAlchemy модели в `app/models/`:
   - `organization.py` — Organization
   - `branch.py` — Branch
   - `user.py` — User (с enum для ролей)
   - `client.py` — Client
   - `visit.py` — Visit
   - `daily_rating.py` — DailyRating
   - `pvr_record.py` — PVRRecord
   - `review.py` — Review (с enum для статусов)
   - `plan.py` — Plan
   - `report.py` — Report
   - `config.py` — RatingConfig, PVRConfig, NotificationConfig
2. Создать `app/models/base.py` с базовым классом: id (UUID), created_at, updated_at
3. Создать `app/models/__init__.py` с импортами всех моделей
4. Добавить все индексы и constraints из data-model.md
5. Все денежные поля — INTEGER (копейки)
6. Все таблицы содержат organization_id
7. Создать и применить Alembic миграцию

**Проверка:** `alembic upgrade head` выполняется без ошибок. Все таблицы созданы в PostgreSQL.

---

## Фаза 2: Аутентификация

### Шаг 2.1: Telegram Auth + JWT + RBAC

**Прочитать:** `docs/api/endpoints.md` (секция Auth)

**Задачи:**
1. Создать `app/auth/telegram.py`:
   - Функция `validate_init_data(init_data: str, bot_token: str) -> dict`
   - Проверка HMAC-SHA256 подписи по алгоритму Telegram
   - Парсинг user data из init_data
2. Создать `app/auth/jwt.py`:
   - `create_access_token(user_id, org_id, role) -> str`
   - `decode_access_token(token: str) -> TokenPayload`
   - TTL: 24 часа
3. Создать `app/auth/dependencies.py`:
   - `get_current_user(token) -> User` — FastAPI Depends
   - `require_role(*roles) -> Depends` — проверка роли
   - `get_org_id(user) -> UUID` — для фильтрации по организации
4. Создать Pydantic-схемы: `app/schemas/auth.py`
5. Создать роутер: `app/api/auth.py`
   - `POST /api/v1/auth/telegram`
   - `GET /api/v1/auth/me`
6. Написать тесты: `tests/test_auth.py`

**Проверка:** POST /auth/telegram с валидным initData возвращает JWT. Невалидный → 401. Проверка ролей работает.

---

## Фаза 3: Синхронизация с YClients

### Шаг 3.1: YClients API клиент

**Прочитать:** `docs/architecture/sync.md`

**Задачи:**
1. Создать `app/integrations/yclients/client.py` — YClientsClient:
   - async HTTP-клиент на httpx
   - Методы: get_records(), get_record(), get_staff(), get_services(), get_clients()
   - Rate limiting: asyncio.Semaphore (10 req/sec)
   - Retry: 3 попытки с backoff (10s, 30s, 90s)
2. Создать `app/integrations/yclients/schemas.py` — Pydantic-модели ответов YClients
3. Написать тесты с моками

**Проверка:** Тесты проходят. Клиент парсит ответы, ретраит, соблюдает rate limit.

---

### Шаг 3.2: Sync Service

**Прочитать:** `docs/architecture/sync.md` (маппинг данных)

**Задачи:**
1. Создать `app/services/sync.py` — SyncService:
   - `sync_records(branch_id, date_from, date_to)`
   - `sync_staff(branch_id)`
   - `sync_clients(branch_id, client_ids)`
   - `initial_sync(org_id)`
2. Маппинг YClients -> локальные модели
3. Определение допов по списку из rating_config.extra_services
4. UPSERT через ON CONFLICT
5. Тесты: маппинг, допы, товары, UPSERT

**Проверка:** sync_records() создаёт Visit с правильными extras_count и products_count.

---

### Шаг 3.3: Webhook receiver

**Задачи:**
1. `POST /api/v1/webhooks/yclients` — приём и обработка webhooks
2. Валидация подписи
3. Быстрый ответ 200 OK, обработка в фоне через Celery
4. После обработки — триггер Rating Engine и PVR Service
5. Логирование всех webhooks

**Проверка:** POST с payload создаёт/обновляет Visit. Рейтинг пересчитывается.

---

### Шаг 3.4: Polling и полная синхронизация (Celery)

**Задачи:**
1. Настроить Celery + Redis
2. Задача `poll_yclients` — каждые 10 минут
3. Задача `full_sync` — ежедневно в 04:00
4. Celery Beat расписание
5. Docker: celery-worker + celery-beat

**Проверка:** Worker и beat запускаются. Polling видно в логах.

---

## Фаза 4: Barber Kombat (ядро)

### Шаг 4.1: Rating Engine

**Прочитать:** `docs/modules/barber-kombat.md` (полный алгоритм)

**Задачи:**
1. Создать `app/services/rating.py` — RatingEngine:
   - `recalculate(branch_id, date) -> list[DailyRating]`
   - Полный алгоритм: сбор данных → ЧС → нормализация → взвешенная сумма → ранжирование
   - Расчёт призового фонда
   - Сохранение в daily_ratings
   - Кэш в Redis
   - Push через WebSocket
2. Подробные тесты всех сценариев из документации

**Проверка:** Все тесты проходят. Результаты совпадают с примерами.

---

### Шаг 4.2: Kombat API endpoints

**Прочитать:** `docs/api/endpoints.md` (секция Barber Kombat)

**Задачи:**
1. Pydantic-схемы: `app/schemas/kombat.py`
2. Роутер: `app/api/kombat.py` — все endpoints из спецификации
3. Проверка ролей
4. Тесты

**Проверка:** Все endpoints возвращают данные в формате из спецификации.

---

### Шаг 4.3: WebSocket для real-time

**Задачи:**
1. `app/websocket/manager.py` — ConnectionManager
2. WebSocket endpoint: `ws://localhost:8000/ws?token=JWT`
3. Broadcast при пересчёте рейтинга
4. Ping/pong keepalive

**Проверка:** Подключение через wscat. При recalculate() приходит сообщение.

---

## Фаза 5: ПВР

### Шаг 5.1: PVR Service + API

**Прочитать:** `docs/modules/pvr.md`

**Задачи:**
1. `app/services/pvr.py` — PVRService:
   - Расчёт чистой выручки (без товаров и сертификатов)
   - Проверка порогов, определение нового → колокольчик
   - UPSERT в pvr_records
2. Интеграция с SyncService и WebhookReceiver
3. API endpoints: /pvr/{branch_id}/current, /pvr/barber/{barber_id}, /pvr/thresholds
4. Тесты: чистая выручка, пороги, колокольчик только при новом пороге

**Проверка:** Все тесты проходят. API корректен.

---

## Фаза 6: Отчётность

### Шаг 6.1: Report Service + Celery Tasks

**Прочитать:** `docs/modules/reports.md`

**Задачи:**
1. `app/services/reports.py` — ReportService:
   - generate_daily_revenue(), generate_day_to_day(), generate_clients_report()
   - generate_kombat_daily(), generate_kombat_monthly()
   - Сохранение в таблицу reports
2. Celery задачи: generate_daily_reports (22:30), generate_day_to_day (11:00), generate_monthly_reports
3. Celery Beat расписание
4. API endpoints: /reports/revenue, /reports/day-to-day, /reports/clients, /reports/bingo
5. Тесты

**Проверка:** Ручной вызов задач генерирует отчёты. API возвращает данные.

---

## Фаза 7: Планы и отзывы

### Шаг 7.1: Plan Service + API

**Прочитать:** `docs/modules/plans.md`

**Задачи:**
1. `app/services/plans.py` — PlanService: CRUD, update_progress, прогноз, уведомления
2. Интеграция с SyncService
3. API endpoints: CRUD /plans/{branch_id}, /plans/network
4. Тесты

**Проверка:** План создаётся, % обновляется, прогноз рассчитывается.

---

### Шаг 7.2: Review Service + API

**Прочитать:** `docs/modules/reviews.md`

**Задачи:**
1. `app/services/reviews.py` — ReviewService: создание, маршрутизация, обработка
2. Публичный endpoint для формы отзыва (без авторизации)
3. Защищённые endpoints: /reviews/{branch_id}, /reviews/{id}/process, /reviews/alarum
4. Celery: проверка необработанных > 2 часов
5. Тесты

**Проверка:** Отзыв создаётся, негативные в Alarum, обработка меняет статус.

---

## Фаза 8: Настройки

### Шаг 8.1: Config Service + API

**Задачи:**
1. `app/services/config.py` — ConfigService: CRUD конфигов, инвалидация кэша
2. API: /config/rating-weights, /config/pvr-thresholds, /config/branches, /config/users, /config/notifications
3. Seed-скрипт: `app/cli.py` — создание начальных данных
4. Тесты: изменение весов → рейтинг пересчитывается

**Проверка:** Настройки сохраняются и влияют на расчёты.

---

## Фаза 9: Telegram-бот

### Шаг 9.1: Telegram Bot

**Прочитать:** `docs/frontend/telegram-bot.md`

**Задачи:**
1. `app/integrations/telegram/bot.py`:
   - send_kombat_report(), send_pvr_bell(), send_negative_review()
   - send_revenue_report(), send_day_to_day()
   - Форматирование MarkdownV2
   - Inline-кнопки с deep link на Mini App
2. Интеграция с Celery задачами отчётности
3. `app/tasks/notifications.py` — задачи отправки
4. Тесты с моками

**Проверка:** Бот отправляет форматированные сообщения с кнопками.

---

## Фаза 10: Frontend — Mini App

### Шаг 10.1: Каркас React-приложения

**Прочитать:** `docs/frontend/screens.md` (общие принципы)

**Задачи:**
1. Telegram Web App SDK: @telegram-apps/sdk
2. Авторизация: initData → POST /auth/telegram → JWT
3. API клиент: axios с JWT
4. Zustand сторы: authStore, kombatStore, pvrStore
5. Роутинг по ролям: BarberLayout, ChefLayout, OwnerLayout, AdminLayout
6. TabBar компонент (конфигурируемый по роли)
7. LoadingSkeleton, ErrorBoundary
8. Telegram тема: цвета из themeParams
9. BackButton для навигации

**Проверка:** Mini App открывается в Telegram, авторизация проходит, tab bar показывается.

---

### Шаг 10.2: Экраны барбера

**Прочитать:** `docs/frontend/screens.md` (Роль: Барбер)

**Задачи:**
1. `useWebSocket` хук — подключение, reconnect
2. `useKombatRating` хук — загрузка + real-time
3. KombatScreen — таблица, анимации, призовой фонд, план
4. ProgressScreen — шкала ПВР, статистика
5. HistoryScreen — календарь с медалями, архив месяцев

**Проверка:** Рейтинг обновляется в реальном времени. ПВР шкала корректна.

---

### Шаг 10.3: Экраны шеф-барбера

**Прочитать:** `docs/frontend/screens.md` (Роль: Шеф-барбер)

**Задачи:**
1. BranchScreen — выручка, план, Бинго, отзывы
2. ReviewProcessModal — модалка обработки отзыва
3. Переиспользование экранов барбера

**Проверка:** Шеф видит Комбат + вкладку Филиал с Бинго и отзывами.

---

### Шаг 10.4: Экраны владельца

**Прочитать:** `docs/frontend/screens.md` (Роль: Владелец)

**Задачи:**
1. DashboardScreen — карточки филиалов, drill-down
2. ReportsScreen — типы отчётов, фильтры, графики (Recharts)
3. CompetitionsScreen — Комбат по филиалам, ПВР по сети
4. SettingsScreen — веса, пороги, планы, сотрудники, уведомления

**Проверка:** Дашборд с филиалами, drill-down работает, настройки сохраняются.

---

### Шаг 10.5: Экраны администратора

**Прочитать:** `docs/frontend/screens.md` (Роль: Администратор)

**Задачи:**
1. MetricsScreen — статистика
2. TasksScreen — чеклист задач
3. HistoryScreen — архив

**Проверка:** Администратор видит показатели и задачи.

---

### Шаг 10.6: Deep Linking

**Задачи:**
1. Парсинг startapp параметра
2. Навигация: kombat_{branch_id}, review_{id}, report_{type}_{date}
3. Тестирование

**Проверка:** Клик "Подробнее" в Telegram → Mini App на нужном экране.

---

## Фаза 11: Жизненный цикл

### Шаг 11.1: Месячный цикл

**Задачи:**
1. Celery задача `monthly_reset` (1-го числа в 00:05):
   - Финализация рейтингов, определение чемпионов
   - Фиксация призовых фондов
   - Новые pvr_records с нулями
   - Новые plans (если установлены)
2. CLI: `python -m app.cli monthly-reset --month=YYYY-MM`
3. Тесты: обнуление, сохранение истории

**Проверка:** После обнуления рейтинги пустые, ПВР = 0, история сохранена.

---

## Фаза 12: Тестирование и деплой

### Шаг 12.1: Интеграционные тесты

**Задачи:**
1. E2E тесты полного цикла:
   - Webhook → Sync → Rating → WebSocket → API
   - Webhook → Sync → PVR → Колокольчик → Telegram
   - Отчёт по расписанию → генерация → API
2. Нагрузочные тесты: 50 WebSocket-соединений
3. Edge cases: пустые филиалы, один барбер, переход месяца

---

### Шаг 12.2: Production Docker + Deploy

**Задачи:**
1. Production Dockerfiles (multi-stage)
2. docker-compose.yml (production)
3. Nginx: SSL, reverse proxy, WebSocket upgrade
4. Production .env
5. Скрипт деплоя
6. Настройка бэкапов PostgreSQL (pg_dump, cron)
7. Health-check мониторинг

---

### Шаг 12.3: Seed данные и первый запуск

**Задачи:**
1. CLI: `python -m app.cli seed` — создание организации, филиалов, пользователей, конфигов
2. CLI: `python -m app.cli sync-initial` — начальная синхронизация с YClients
3. README.md с инструкцией первого запуска
4. Проверка: Mini App с реальными данными

---

## Чеклист готовности к запуску

- [ ] Все API endpoints возвращают корректные данные
- [ ] WebSocket обновляет рейтинг в реальном времени
- [ ] Telegram-бот отправляет все типы уведомлений
- [ ] Deep linking работает
- [ ] Все 4 роли видят свои экраны
- [ ] Настройки сохраняются и влияют на расчёты
- [ ] Celery Beat выполняет задачи по расписанию
- [ ] Polling работает как fallback для webhooks
- [ ] Месячное обнуление работает корректно
- [ ] SSL настроен, Mini App через HTTPS
- [ ] Бэкапы PostgreSQL настроены (ежедневно)
- [ ] Мониторинг работает (health check, Sentry, логи)
- [ ] Документация актуальна
