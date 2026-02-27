# Модель данных

## ER-диаграмма (основные сущности)

```
Organization (1) ──── (N) Branch
Organization (1) ──── (N) User
Organization (1) ──── (1) RatingConfig
Organization (1) ──── (1) PVRConfig

Branch (1) ──── (N) User
Branch (1) ──── (N) Visit
Branch (1) ──── (N) DailyRating
Branch (1) ──── (N) Plan
Branch (1) ──── (N) Report
Branch (1) ──── (N) AdminRating

User (1) ──── (N) Visit          [как барбер]
User (1) ──── (N) DailyRating
User (1) ──── (N) PVRRecord
User (1) ──── (N) AdminRating    [как администратор]

Visit (1) ──── (0..1) Review
Visit (N) ──── (1) Client

Client (1) ──── (N) Visit
Client (1) ──── (N) Review
```

## Таблицы

### organizations

Корневая сущность. Каждый клиент системы (сеть барбершопов) — отдельная организация.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | Уникальный идентификатор |
| name | VARCHAR(255) | Название сети |
| slug | VARCHAR(100) UNIQUE | URL-совместимое имя |
| settings | JSONB | Общие настройки (часовой пояс, валюта и т.д.) |
| is_active | BOOLEAN | Активна ли подписка |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### branches

Филиал (точка) сети.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| name | VARCHAR(255) | Название филиала ("8 марта", "Космос") |
| address | VARCHAR(500) | Адрес |
| yclients_company_id | INTEGER | ID компании в YClients |
| telegram_group_id | BIGINT NULL | ID Telegram-группы филиала (для уведомлений) |
| is_active | BOOLEAN | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Индексы:** organization_id, yclients_company_id

### users

Все пользователи системы: барберы, шеф-барберы, администраторы, управляющие, владельцы.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| branch_id | UUID (FK → branches) NULL | NULL для владельцев/управляющих сетью |
| telegram_id | BIGINT UNIQUE | Telegram ID пользователя |
| role | ENUM('owner','manager','chef','barber','admin') | Роль в системе |
| name | VARCHAR(255) | Имя (отображаемое) |
| grade | VARCHAR(50) NULL | Грейд барбера (junior, middle, senior, top) |
| haircut_price | INTEGER NULL | Цена стрижки (для расчёта ЧС). Только для барберов |
| yclients_staff_id | INTEGER NULL | ID сотрудника в YClients |
| is_active | BOOLEAN | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Индексы:** organization_id, branch_id, telegram_id, yclients_staff_id, role

### clients

Клиенты барбершопов. Синхронизируются из YClients.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| yclients_client_id | INTEGER | ID клиента в YClients |
| phone | VARCHAR(20) | Телефон (хешированный для хранения, открытый для поиска) |
| name | VARCHAR(255) | Имя |
| birthday | DATE NULL | Дата рождения |
| first_visit_at | TIMESTAMP NULL | Дата первого визита |
| last_visit_at | TIMESTAMP NULL | Дата последнего визита |
| total_visits | INTEGER DEFAULT 0 | Всего визитов |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Индексы:** organization_id, yclients_client_id, phone

### visits

Визиты (записи) клиентов. Основа для всех расчётов. Синхронизируются из YClients.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| branch_id | UUID (FK → branches) | |
| barber_id | UUID (FK → users) | Барбер, обслуживший клиента |
| client_id | UUID (FK → clients) NULL | |
| yclients_record_id | INTEGER | ID записи в YClients |
| date | DATE | Дата визита |
| revenue | INTEGER | Общая выручка визита (в копейках) |
| services_revenue | INTEGER | Выручка за услуги (в копейках) |
| products_revenue | INTEGER | Выручка за товары (в копейках) |
| services | JSONB | Детализация услуг: [{name, price, is_extra}] |
| products | JSONB | Детализация товаров: [{name, price, quantity}] |
| extras_count | INTEGER DEFAULT 0 | Количество доп. услуг |
| products_count | INTEGER DEFAULT 0 | Количество проданных товаров (штуки) |
| payment_type | VARCHAR(20) | Тип оплаты: card, cash, qr, certificate |
| status | VARCHAR(20) | Статус: completed, cancelled, no_show |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Индексы:** organization_id, branch_id, barber_id, date, yclients_record_id
**Составной индекс:** (branch_id, date) — основной запрос для рейтингов

### daily_ratings

Рейтинги Barber Kombat. Один ряд = один барбер за один день.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| branch_id | UUID (FK → branches) | |
| barber_id | UUID (FK → users) | |
| date | DATE | |
| revenue | INTEGER | Выручка в копейках |
| revenue_score | FLOAT | Нормализованный % (0-100) |
| cs_value | FLOAT | Среднее значение ЧС за день |
| cs_score | FLOAT | Нормализованный % (0-100) |
| products_count | INTEGER | Кол-во товаров (штуки) |
| products_score | FLOAT | Нормализованный % |
| extras_count | INTEGER | Кол-во допов (штуки) |
| extras_score | FLOAT | Нормализованный % |
| reviews_avg | FLOAT NULL | Средняя оценка отзывов |
| reviews_score | FLOAT | Нормализованный % |
| total_score | FLOAT | Итоговый взвешенный рейтинг (0-100) |
| rank | INTEGER | Место в филиале за день (1, 2, 3...) |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Индексы:** (branch_id, date), (barber_id, date)
**Уникальный:** (barber_id, date)

### pvr_records

Записи о премиях ПВР. Один ряд = один барбер за один месяц.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| barber_id | UUID (FK → users) | |
| month | DATE | Первое число месяца (2024-10-01) |
| cumulative_revenue | INTEGER | Накопительная чистая выручка (в копейках) |
| current_threshold | INTEGER NULL | Текущий достигнутый порог (в копейках) |
| bonus_amount | INTEGER DEFAULT 0 | Начисленная премия (в копейках) |
| thresholds_reached | JSONB | История достижений: [{threshold, reached_at}] |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Уникальный:** (barber_id, month)

### reviews

Отзывы клиентов.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| branch_id | UUID (FK → branches) | |
| barber_id | UUID (FK → users) | |
| visit_id | UUID (FK → visits) NULL | |
| client_id | UUID (FK → clients) NULL | |
| rating | INTEGER | Оценка 1-5 |
| comment | TEXT NULL | Комментарий клиента |
| source | VARCHAR(20) | Источник: internal, yandex_maps, google, 2gis |
| status | ENUM('new','in_progress','processed') | Статус обработки |
| processed_by | UUID (FK → users) NULL | Кто обработал |
| processed_comment | TEXT NULL | Комментарий обработки |
| processed_at | TIMESTAMP NULL | Время обработки |
| created_at | TIMESTAMP | |

**Индексы:** (branch_id, created_at), (barber_id, created_at), status

### plans

Планы выручки по филиалам.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| branch_id | UUID (FK → branches) | |
| month | DATE | Первое число месяца |
| target_amount | INTEGER | Плановая выручка (в копейках) |
| current_amount | INTEGER DEFAULT 0 | Текущая накопительная выручка |
| percentage | FLOAT DEFAULT 0 | Процент выполнения |
| forecast_amount | INTEGER NULL | Прогноз на конец месяца |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Уникальный:** (branch_id, month)

### reports

Хранение сгенерированных отчётов.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| branch_id | UUID (FK → branches) NULL | NULL для отчётов по всей сети |
| type | VARCHAR(50) | Тип: daily_revenue, day_to_day, clients, kombat_daily, kombat_monthly, pvr |
| date | DATE | Дата отчёта |
| data | JSONB | Содержимое отчёта |
| delivered_telegram | BOOLEAN DEFAULT FALSE | Отправлен ли в Telegram |
| delivered_at | TIMESTAMP NULL | Время отправки |
| created_at | TIMESTAMP | |

**Индексы:** (organization_id, type, date), (branch_id, type, date)

### rating_configs

Настройки весов рейтинга Barber Kombat. Одна запись на организацию.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) UNIQUE | |
| revenue_weight | INTEGER DEFAULT 20 | Вес выручки (%) |
| cs_weight | INTEGER DEFAULT 20 | Вес ЧС (%) |
| products_weight | INTEGER DEFAULT 25 | Вес товаров (%) |
| extras_weight | INTEGER DEFAULT 25 | Вес допов (%) |
| reviews_weight | INTEGER DEFAULT 10 | Вес отзывов (%) |
| prize_gold_pct | FLOAT DEFAULT 0.5 | % призового фонда за 1-е место |
| prize_silver_pct | FLOAT DEFAULT 0.3 | % за 2-е место |
| prize_bronze_pct | FLOAT DEFAULT 0.1 | % за 3-е место |
| extra_services | JSONB | Список допов: ["воск", "камуфляж", "массаж"...] |
| updated_at | TIMESTAMP | |

**Constraint:** revenue_weight + cs_weight + products_weight + extras_weight + reviews_weight = 100

### pvr_configs

Настройки порогов ПВР. Одна запись на организацию.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) UNIQUE | |
| thresholds | JSONB | Массив: [{"amount": 30000000, "bonus": 1000000}, ...] (в копейках) |
| count_products | BOOLEAN DEFAULT FALSE | Считать ли товары в чистую выручку |
| count_certificates | BOOLEAN DEFAULT FALSE | Считать ли сертификаты |
| updated_at | TIMESTAMP | |

### notification_configs

Настройки уведомлений.

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID (PK) | |
| organization_id | UUID (FK → organizations) | |
| branch_id | UUID (FK → branches) NULL | NULL = настройка для всей сети |
| notification_type | VARCHAR(50) | Тип уведомления |
| telegram_chat_id | BIGINT | ID чата/группы для отправки |
| is_enabled | BOOLEAN DEFAULT TRUE | |
| schedule_time | TIME NULL | Время отправки (для отчётов по расписанию) |
| created_at | TIMESTAMP | |

## Хранение денежных сумм

**Все денежные суммы хранятся в копейках (INTEGER).** Это исключает проблемы с плавающей точкой. Конвертация в рубли — только на уровне фронтенда при отображении.

Пример: 150000 рублей = 15000000 (в БД)

## Мультитенантность

Каждая таблица содержит `organization_id`. Все запросы фильтруются по organization_id. Это обеспечивается:
1. Middleware на уровне API — извлекает org_id из JWT
2. Базовый класс запросов — автоматически добавляет WHERE organization_id = ?
3. Row Level Security в PostgreSQL (опционально, для дополнительной защиты)
