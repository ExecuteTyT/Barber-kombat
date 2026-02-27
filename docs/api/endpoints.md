# REST API спецификация

## Общее

- Base URL: `https://api.your-domain.com/api/v1`
- Формат: JSON
- Авторизация: `Authorization: Bearer {jwt_token}`
- Все денежные суммы в копейках (INTEGER)
- Все даты в ISO 8601 формате
- Пагинация: `?page=1&per_page=20`
- Ошибки: `{ "error": "описание", "code": "ERROR_CODE" }`

## Коды ошибок

| HTTP | Код | Описание |
|------|-----|----------|
| 401 | UNAUTHORIZED | Невалидный или просроченный токен |
| 403 | FORBIDDEN | Недостаточно прав для действия |
| 404 | NOT_FOUND | Ресурс не найден |
| 422 | VALIDATION_ERROR | Ошибка валидации входных данных |
| 500 | INTERNAL_ERROR | Внутренняя ошибка сервера |

## Auth

### POST /auth/telegram

Авторизация через Telegram initData.

**Request:**
```json
{
    "init_data": "query_id=AAH...&user={...}&auth_date=1697200000&hash=abc123..."
}
```

**Response (200):**
```json
{
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
        "id": "uuid",
        "name": "Павел",
        "role": "barber",
        "branch_id": "uuid",
        "organization_id": "uuid"
    }
}
```

### GET /auth/me

Текущий пользователь.

**Response (200):**
```json
{
    "id": "uuid",
    "telegram_id": 123456789,
    "name": "Павел",
    "role": "barber",
    "branch_id": "uuid",
    "branch_name": "8 марта",
    "organization_id": "uuid",
    "grade": "senior",
    "haircut_price": 200000
}
```

## Barber Kombat

### GET /kombat/today/{branch_id}

Текущий рейтинг дня. Доступен всем ролям.

**Query params:** нет

**Response (200):**
```json
{
    "branch_id": "uuid",
    "branch_name": "8 марта",
    "date": "2024-10-13",
    "is_active": true,
    "ratings": [
        {
            "barber_id": "uuid",
            "name": "Павел",
            "rank": 1,
            "total_score": 100.0,
            "revenue": 1350000,
            "revenue_score": 100.0,
            "cs_value": 1.45,
            "cs_score": 95.4,
            "products_count": 0,
            "products_score": 0.0,
            "extras_count": 2,
            "extras_score": 100.0,
            "reviews_avg": null,
            "reviews_score": 0.0
        },
        {
            "barber_id": "uuid",
            "name": "Лев",
            "rank": 2,
            "total_score": 94.0,
            "revenue": 1230000,
            "revenue_score": 91.1,
            "cs_value": 1.52,
            "cs_score": 100.0,
            "products_count": 0,
            "products_score": 0.0,
            "extras_count": 1,
            "extras_score": 50.0,
            "reviews_avg": null,
            "reviews_score": 0.0
        }
    ],
    "prize_fund": {
        "gold": 490000,
        "silver": 294000,
        "bronze": 98000
    },
    "plan": {
        "target": 240000000,
        "current": 185000000,
        "percentage": 77.1,
        "forecast": 235000000,
        "required_daily": 3670000
    },
    "weights": {
        "revenue": 20,
        "cs": 20,
        "products": 25,
        "extras": 25,
        "reviews": 10
    }
}
```

### GET /kombat/standings/{branch_id}

Общий зачёт побед за месяц.

**Query params:** `month=2024-10` (опционально, по умолчанию текущий)

**Response (200):**
```json
{
    "branch_id": "uuid",
    "month": "2024-10",
    "standings": [
        {"barber_id": "uuid", "name": "Павел", "wins": 7, "avg_score": 95.2},
        {"barber_id": "uuid", "name": "Лев", "wins": 4, "avg_score": 88.1},
        {"barber_id": "uuid", "name": "Марк", "wins": 2, "avg_score": 82.5}
    ]
}
```

### GET /kombat/history/{branch_id}

История рейтингов. Роли: шеф, владелец.

**Query params:** `date_from=2024-10-01&date_to=2024-10-13`

**Response (200):**
```json
{
    "days": [
        {
            "date": "2024-10-13",
            "winner": {"barber_id": "uuid", "name": "Павел"},
            "ratings": [...]
        }
    ]
}
```

### GET /kombat/barber/{barber_id}/stats

Детальная статистика барбера. Доступен всем.

**Query params:** `month=2024-10`

**Response (200):**
```json
{
    "barber_id": "uuid",
    "name": "Павел",
    "month": "2024-10",
    "wins": 7,
    "avg_score": 95.2,
    "total_revenue": 520000000,
    "avg_revenue_per_day": 40000000,
    "avg_cs": 1.48,
    "total_products": 5,
    "total_extras": 23,
    "avg_review": 4.8,
    "daily_scores": [
        {"date": "2024-10-01", "score": 100, "rank": 1},
        {"date": "2024-10-02", "score": 87, "rank": 2},
        ...
    ]
}
```

## ПВР

### GET /pvr/{branch_id}/current

Накопительная выручка всех барберов филиала. Роли: шеф, владелец.

**Response (200):**
```json
{
    "branch_id": "uuid",
    "month": "2024-10",
    "barbers": [
        {
            "barber_id": "uuid",
            "name": "Павел",
            "cumulative_revenue": 52000000,
            "current_threshold": 50000000,
            "bonus_amount": 3000000,
            "next_threshold": 60000000,
            "remaining_to_next": 8000000,
            "thresholds_reached": [
                {"amount": 30000000, "reached_at": "2024-10-05"},
                {"amount": 35000000, "reached_at": "2024-10-08"},
                {"amount": 40000000, "reached_at": "2024-10-11"},
                {"amount": 50000000, "reached_at": "2024-10-13"}
            ]
        }
    ]
}
```

### GET /pvr/barber/{barber_id}

ПВР конкретного барбера. Доступен всем (барбер видит только себя).

**Response:** аналогично элементу массива выше.

## Отчёты

### GET /reports/revenue/{branch_id}

**Query params:** `date_from=2024-10-01&date_to=2024-10-13`

**Response (200):**
```json
{
    "branch_id": "uuid",
    "branch_name": "8 марта",
    "period": {"from": "2024-10-01", "to": "2024-10-13"},
    "daily": [
        {"date": "2024-10-01", "revenue": 8500000},
        {"date": "2024-10-02", "revenue": 7200000},
        ...
    ],
    "total": 185000000,
    "avg_daily": 14230769
}
```

### GET /reports/revenue/network

**Query params:** `date_from=2024-10-01&date_to=2024-10-13`

### GET /reports/day-to-day/{branch_id}

**Response (200):**
```json
{
    "branch_id": "uuid",
    "current_day": 13,
    "months": [
        {
            "name": "Октябрь 2024",
            "cumulative": [{"day": 1, "amount": 8500000}, ...]
        },
        {
            "name": "Сентябрь 2024",
            "cumulative": [...]
        },
        {
            "name": "Август 2024",
            "cumulative": [...]
        }
    ],
    "comparison": {
        "vs_prev_month": 14.3,
        "vs_prev_prev_month": -2.1
    }
}
```

### GET /reports/clients/{branch_id}

**Query params:** `date=2024-10-13` или `month=2024-10`

### GET /reports/bingo

Все барберы сети с накопительной выручкой. Роль: владелец.

**Response (200):**
```json
{
    "month": "2024-10",
    "barbers": [
        {
            "barber_id": "uuid",
            "name": "Иванов П.",
            "branch_name": "8 марта",
            "cumulative_revenue": 52000000,
            "pvr_threshold": 50000000,
            "pvr_bonus": 3000000,
            "in_shift_today": true
        }
    ],
    "summary": {
        "total_barbers": 45,
        "in_shift_today": 32,
        "total_revenue_mtd": 925000000
    }
}
```

## Планы

### GET /plans/{branch_id}

### PUT /plans/{branch_id}

Роль: владелец.

**Request:**
```json
{
    "month": "2024-10-01",
    "target_amount": 240000000
}
```

### GET /plans/network

Все планы по сети.

## Отзывы

### GET /reviews/{branch_id}

**Query params:** `status=new&rating_max=3&date_from=2024-10-01&page=1`

### PUT /reviews/{review_id}/process

**Request:**
```json
{
    "status": "processed",
    "comment": "Позвонили клиенту, извинились, предложили бесплатную стрижку"
}
```

### GET /reviews/alarum

Необработанные негативные отзывы по всей сети. Роли: шеф (свой филиал), владелец (все).

## Настройки

### GET/PUT /config/rating-weights

```json
{
    "revenue_weight": 20,
    "cs_weight": 20,
    "products_weight": 25,
    "extras_weight": 25,
    "reviews_weight": 10,
    "prize_gold_pct": 0.5,
    "prize_silver_pct": 0.3,
    "prize_bronze_pct": 0.1,
    "extra_services": ["воск", "камуфляж головы", "камуфляж бороды", "массаж", "премиум помывка"]
}
```

### GET/PUT /config/pvr-thresholds

```json
{
    "thresholds": [
        {"amount": 30000000, "bonus": 1000000},
        {"amount": 35000000, "bonus": 1500000},
        {"amount": 40000000, "bonus": 2000000},
        {"amount": 50000000, "bonus": 3000000},
        {"amount": 60000000, "bonus": 4000000},
        {"amount": 80000000, "bonus": 5000000}
    ],
    "count_products": false,
    "count_certificates": false
}
```

### CRUD /config/branches, /config/users

Стандартные CRUD операции. Роль: владелец.

## WebSocket

**Endpoint:** `wss://api.your-domain.com/ws?token={jwt_token}`

### События (Server → Client)

```json
{"type": "rating_update", "branch_id": "uuid", "ratings": [...], "prize_fund": {...}}
{"type": "pvr_threshold", "branch_id": "uuid", "barber_name": "Павел", "threshold": 50000000, "bonus": 3000000}
{"type": "new_review", "branch_id": "uuid", "review": {...}}
{"type": "plan_update", "branch_id": "uuid", "percentage": 77.1}
```

### Подписка

Клиент автоматически получает события для своей организации. Фильтрация по branch_id — на стороне клиента (или по параметру подписки).
