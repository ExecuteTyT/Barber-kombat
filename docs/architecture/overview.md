# Архитектура системы

## Высокоуровневая схема

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Mini App                     │
│                  (React + TypeScript)                    │
│    ┌──────────┬──────────┬──────────┬──────────┐       │
│    │  Барбер  │   Шеф    │ Владелец │  Админ   │       │
│    └────┬─────┴────┬─────┴────┬─────┴────┬─────┘       │
└─────────┼──────────┼──────────┼──────────┼──────────────┘
          │          │          │          │
          ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────┐
│                   Nginx (SSL proxy)                      │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌────────────────┐ ┌───────────┐ ┌───────────────┐
│  FastAPI REST  │ │ WebSocket │ │ Webhook       │
│  API Server    │ │ Server    │ │ Receiver      │
└───────┬────────┘ └─────┬─────┘ └──────┬────────┘
        │                │              │
        ▼                ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                   Service Layer                          │
│  ┌──────────┐ ┌─────┐ ┌────────┐ ┌──────┐ ┌────────┐  │
│  │ Rating   │ │ PVR │ │Reports │ │Plans │ │Reviews │  │
│  │ Engine   │ │     │ │        │ │      │ │        │  │
│  └────┬─────┘ └──┬──┘ └───┬────┘ └──┬───┘ └───┬────┘  │
└───────┼──────────┼────────┼─────────┼─────────┼────────┘
        │          │        │         │         │
        ▼          ▼        ▼         ▼         ▼
┌─────────────────────────────────────────────────────────┐
│                   Data Layer                             │
│  ┌──────────────────┐  ┌─────────────────────────┐     │
│  │   PostgreSQL     │  │   Redis                  │     │
│  │   (основные      │  │   (кэш рейтингов,       │     │
│  │    данные)       │  │    сессии, очереди)      │     │
│  └──────────────────┘  └─────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
┌────────────────┐              ┌──────────────────────┐
│  Celery Worker │              │  Celery Beat         │
│  (фоновые      │              │  (расписание:        │
│   задачи)      │              │   отчёты, polling,   │
│                │              │   синхронизация)     │
└───────┬────────┘              └──────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│              External Integrations                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ YClients │  │ Telegram Bot │  │ WhatsApp (опц.)  │  │
│  │ API      │  │ API          │  │ Business API     │  │
│  └──────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Сервисные модули бэкенда

### Auth Service
- Авторизация через Telegram Web App initData
- Валидация подписи Telegram на сервере
- Выдача JWT-токенов (TTL: 24 часа)
- RBAC: owner, manager, chef, barber, admin
- Middleware для проверки роли на каждом endpoint

### Sync Service
- Получение данных из YClients через REST API и webhooks
- Двойная синхронизация: webhooks (primary) + polling (fallback)
- Polling каждые 10 минут: запрос данных за последние 20 минут
- Полная синхронизация: ежедневно в 04:00 (сверка за предыдущий день)
- Маппинг сущностей YClients → локальные модели
- Подробности: см. `docs/architecture/sync.md`

### Rating Engine
- Расчёт рейтингов Barber Kombat в реальном времени
- Триггер: каждое обновление данных от Sync Service
- Алгоритм: нормализация → взвешенная сумма → ранжирование
- Кэширование текущих рейтингов в Redis
- Push обновлений через WebSocket
- Подробности: см. `docs/modules/barber-kombat.md`

### PVR Service
- Отслеживание накопительной чистой выручки с 1-го числа месяца
- Проверка порогов при каждом обновлении
- Генерация уведомлений (колокольчиков) при достижении порога
- Подробности: см. `docs/modules/pvr.md`

### Report Service
- Генерация отчётов по расписанию (Celery Beat)
- Два канала доставки: Telegram-бот + Mini App
- Хранение истории отчётов в БД
- Подробности: см. `docs/modules/reports.md`

### Plan Service
- CRUD планов по филиалам
- Автоматический расчёт % выполнения
- Линейный прогноз на конец месяца
- Уведомления при критических отклонениях
- Подробности: см. `docs/modules/plans.md`

### Review Service
- Отправка запросов отзывов после визитов
- Сбор оценок, маршрутизация негатива в Alarum
- Подробности: см. `docs/modules/reviews.md`

### Notification Service
- Единая точка отправки всех уведомлений
- Каналы: Telegram Bot API (группы, личные чаты) + WebSocket (Mini App)
- Очередь через Celery для надёжной доставки
- Deep linking: кнопки в сообщениях бота открывают Mini App на нужном экране

### Config Service
- CRUD настроек организации
- Веса рейтингов, пороги ПВР, призовые проценты
- Управление филиалами и сотрудниками
- Все настройки кэшируются в Redis, инвалидируются при изменении

## Docker Compose (Development)

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db, redis]
    env_file: .env
    volumes: ["./backend:/app"]

  celery-worker:
    build: ./backend
    command: celery -A app.tasks worker -l info
    depends_on: [db, redis]
    env_file: .env

  celery-beat:
    build: ./backend
    command: celery -A app.tasks beat -l info
    depends_on: [db, redis]
    env_file: .env

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    volumes: ["./frontend/src:/app/src"]

  db:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: barber_kombat
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    depends_on: [backend, frontend]

volumes:
  pgdata:
```

## Переменные окружения

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/barber_kombat

# Redis
REDIS_URL=redis://redis:6379/0

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_MINI_APP_URL=https://your-domain.com

# YClients
YCLIENTS_PARTNER_TOKEN=your_partner_token
YCLIENTS_USER_TOKEN=your_user_token
YCLIENTS_COMPANY_ID=your_company_id
YCLIENTS_WEBHOOK_SECRET=your_webhook_secret

# WhatsApp (опционально)
WHATSAPP_API_URL=https://api.provider.com
WHATSAPP_API_TOKEN=your_token

# JWT
JWT_SECRET=your_jwt_secret
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# App
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=INFO
```
