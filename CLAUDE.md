---
description: 
alwaysApply: true
---

# Barber Kombat — Telegram Mini App

## О проекте

Barber Kombat — автоматизированная система управления и мотивации персонала для сети барбершопов. Реализуется как Telegram Mini App с серверным бэкендом.

Система объединяет в едином интерфейсе:
- Геймификацию работы барберов (ежедневные соревнования с денежными призами)
- Систему премирования за высокие результаты (ПВР)
- Автоматическую отчётность для владельца и управляющих
- Планирование и контроль выручки
- Сбор и обработку отзывов клиентов
- Telegram-бот для push-уведомлений

## Технологический стек

### Backend
- **Язык:** Python 3.12+
- **Фреймворк:** FastAPI
- **База данных:** PostgreSQL 16
- **Кэш / Брокер:** Redis 7
- **Фоновые задачи:** Celery + Redis как брокер
- **ORM:** SQLAlchemy 2.0 + Alembic (миграции)
- **Валидация:** Pydantic v2
- **WebSocket:** FastAPI WebSocket (встроенный)
- **HTTP-клиент:** httpx (async)
- **Тестирование:** pytest + pytest-asyncio

### Frontend
- **Фреймворк:** React 18 + TypeScript
- **Сборка:** Vite
- **Стейт-менеджер:** Zustand
- **UI:** Tailwind CSS + кастомные компоненты (адаптация под Telegram тему)
- **WebSocket клиент:** встроенный WebSocket API
- **Telegram SDK:** @telegram-apps/sdk
- **HTTP-клиент:** axios
- **Тестирование:** Vitest

### Инфраструктура
- **Контейнеризация:** Docker + Docker Compose
- **Reverse proxy:** Nginx (для Mini App SSL)
- **CI:** GitHub Actions (линтинг, тесты)

## Структура репозитория

```
barber-kombat/
├── CLAUDE.md                  # Этот файл — контекст для Claude Code
├── docs/                      # Документация и ТЗ (разбито по модулям)
│   ├── architecture/
│   │   ├── overview.md        # Общая архитектура
│   │   ├── data-model.md      # Модель данных (ER)
│   │   └── sync.md            # Синхронизация с YClients
│   ├── modules/
│   │   ├── barber-kombat.md   # Модуль Barber Kombat
│   │   ├── pvr.md             # Модуль ПВР
│   │   ├── reports.md         # Модуль отчётности
│   │   ├── plans.md           # Модуль планирования
│   │   └── reviews.md         # Модуль отзывов
│   ├── api/
│   │   └── endpoints.md       # REST API спецификация
│   └── frontend/
│       ├── screens.md         # Экраны по ролям
│       └── telegram-bot.md    # Telegram-бот уведомлений
├── plans/
│   └── development-plan.md    # Пошаговый план разработки
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI application
│   │   ├── config.py          # Настройки приложения
│   │   ├── database.py        # Подключение к БД
│   │   ├── auth/              # Авторизация Telegram
│   │   ├── models/            # SQLAlchemy модели
│   │   ├── schemas/           # Pydantic схемы
│   │   ├── api/               # API роутеры
│   │   ├── services/          # Бизнес-логика
│   │   ├── integrations/      # YClients, Telegram, WhatsApp
│   │   ├── tasks/             # Celery задачи
│   │   └── websocket/         # WebSocket менеджер
│   ├── alembic/               # Миграции БД
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api/               # API клиент
│   │   ├── components/        # Общие компоненты
│   │   ├── screens/           # Экраны по ролям
│   │   │   ├── barber/
│   │   │   ├── chef/
│   │   │   ├── owner/
│   │   │   └── admin/
│   │   ├── stores/            # Zustand сторы
│   │   ├── hooks/             # Кастомные хуки
│   │   ├── types/             # TypeScript типы
│   │   └── utils/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
└── .gitignore
```

## Правила кодирования

### Python (Backend)
- Используй type hints везде
- Async/await для всех I/O операций
- Pydantic v2 для всех входных/выходных схем
- SQLAlchemy 2.0 стиль (select, не query)
- Каждый сервис — отдельный класс с dependency injection через FastAPI Depends
- Логирование через structlog
- Все SQL-запросы через ORM, не raw SQL
- Миграции через Alembic для каждого изменения модели
- Docstrings для публичных методов

### TypeScript (Frontend)
- Строгая типизация, no `any`
- Функциональные компоненты с хуками
- Zustand для глобального состояния
- Кастомные хуки для бизнес-логики (useKombatRating, usePVR, etc.)
- Tailwind для стилей, никакого inline CSS
- Компоненты в отдельных файлах, один компонент = один файл
- Адаптация под Telegram тему (цвета из Telegram.WebApp.themeParams)

### Общие правила
- Все конфигурационные значения — через переменные окружения
- Не хардкодить ID организации, филиала и т.д.
- organization_id в каждой таблице (мультитенантность)
- Комментарии на английском, UI-тексты на русском
- Git: conventional commits (feat:, fix:, refactor:, docs:)

## Внешние интеграции

### YClients API
- Документация: https://api.yclients.com
- Нужен: API ключ + Bearer токен пользователя
- Основные endpoints: records (визиты), staff, services, goods, clients, transactions
- Webhooks: настраиваются в личном кабинете YClients
- **ВАЖНО:** перед реализацией интеграции — изучить реальный API, проверить доступность нужных данных

### Telegram Bot API
- Используем python-telegram-bot или aiogram для бота
- Mini App: @telegram-apps/sdk на фронте
- Авторизация: валидация initData на бэкенде

### WhatsApp Business API
- Через провайдера (Wazzup / GreenAPI)
- Используется ТОЛЬКО для отправки запросов отзывов
- Fallback: Telegram-бот

## Что НЕ входит в текущий скоуп
- Банковская интеграция (модуль отключён)
- Admin Kombat (опциональный модуль, не в MVP)
- Маркетинговый модуль (опциональный)
- Power BI дашборды (опциональный)
- Мобильное приложение (только Telegram Mini App)

## Как работать с этим проектом

1. Перед началом работы над любым модулем — прочитай соответствующий файл из `docs/`
2. Следуй плану из `plans/development-plan.md` — работай последовательно по шагам
3. После каждого шага — проверь, что тесты проходят
4. Не забывай создавать Alembic миграции при изменении моделей
5. Коммить после каждого логического блока работы
