# Модуль автоматической отчётности

## Назначение

Генерация и доставка управленческих отчётов по расписанию. Два канала: Telegram-бот (push) и Mini App (pull).

## Расписание отчётов

| Отчёт | Время | Получатели | Канал |
|-------|-------|-----------|-------|
| Barber Kombat (итоги дня) | 22:30 | Группа филиала | Telegram + Mini App |
| Выручка за день | 22:30 | Владелец, управляющие | Telegram + Mini App |
| Клиенты (новые/повторные) | 22:30 | Владелец, управляющие | Mini App |
| Day-to-day сравнение | 11:00 | Владелец | Telegram + Mini App |
| Barber Kombat (итоги месяца) | Последний день, 23:00 | Группа филиала | Telegram + Mini App |
| ПВР (итоги месяца) | Последний день, 23:00 | Владелец | Mini App |

## Отчёт: Выручка за день

### Данные

```python
{
    "date": "2024-10-13",
    "branches": [
        {
            "branch_id": "uuid",
            "name": "8 марта",
            "revenue_today": 8500000,          # в копейках
            "revenue_mtd": 185000000,           # month-to-date
            "plan_target": 240000000,
            "plan_percentage": 77.1,
            "barbers_in_shift": 3,
            "barbers_total": 4,
        },
        ...
    ],
    "network_total_today": 42500000,
    "network_total_mtd": 925000000,
}
```

### Формат Telegram

```
📊 Выручка — 13 октября

8 марта: 85 000₽ (месяц: 1 850 000₽, план 77%)
Космос: 72 000₽ (месяц: 1 520 000₽, план 84%)
Ленина: 91 000₽ (месяц: 1 980 000₽, план 99%)
...

Итого за день: 425 000₽
Итого за октябрь: 9 250 000₽

[Подробнее →]
```

## Отчёт: Day-to-day сравнение

### Данные

```python
{
    "branch_id": "uuid" | null,  # null = вся сеть
    "period_end": "2024-10-13",
    "current_month": {
        "name": "Октябрь 2024",
        "daily_cumulative": [
            {"day": 1, "amount": 32000000},
            {"day": 2, "amount": 67000000},
            ...
            {"day": 13, "amount": 480000000},
        ]
    },
    "prev_month": {
        "name": "Сентябрь 2024",
        "daily_cumulative": [...]
    },
    "prev_prev_month": {
        "name": "Август 2024",
        "daily_cumulative": [...]
    },
    "comparison": {
        "vs_prev": "+14.3%",   # октябрь vs сентябрь на ту же дату
        "vs_prev_prev": "-2.1%"
    }
}
```

### Формат Telegram (11:00)

```
📈 Day-to-day — Контора

С 1 по 13:
Октябрь 2024: 4 800 000₽ ↑
Сентябрь 2024: 4 200 000₽
Август 2024: 4 900 000₽

vs прошлый месяц: +14.3% ✅
vs позапрошлый: -2.1%

[Подробнее →]
```

## Отчёт: Клиенты

### Данные

```python
{
    "date": "2024-10-13",
    "branches": [
        {
            "branch_id": "uuid",
            "name": "8 марта",
            "new_clients_today": 8,
            "returning_clients_today": 25,
            "total_today": 33,
            "new_clients_mtd": 105,
            "returning_clients_mtd": 706,
            "total_mtd": 811,
        }
    ],
    "network_new_mtd": 651,
    "network_returning_mtd": 4300,
    "network_total_mtd": 4951,
}
```

Определение нового клиента: телефон клиента не встречался в visits ранее (первый визит).

## Отчёт: Barber Kombat (ежедневный и ежемесячный)

Описание: см. `docs/modules/barber-kombat.md`

## Хранение отчётов

Все сгенерированные отчёты сохраняются в таблицу `reports`:
- `type` — тип отчёта
- `data` — JSONB с данными
- `delivered_telegram` — отправлен ли в Telegram
- `delivered_at` — время отправки

В Mini App отчёты загружаются из таблицы reports с фильтрами по типу, дате и филиалу.

## Celery Beat расписание

```python
CELERY_BEAT_SCHEDULE = {
    "polling-yclients": {
        "task": "app.tasks.sync.poll_yclients",
        "schedule": crontab(minute="*/10"),  # каждые 10 минут
    },
    "daily-full-sync": {
        "task": "app.tasks.sync.full_sync",
        "schedule": crontab(hour=4, minute=0),  # 04:00
    },
    "report-day-to-day": {
        "task": "app.tasks.reports.generate_day_to_day",
        "schedule": crontab(hour=11, minute=0),  # 11:00
    },
    "report-daily-evening": {
        "task": "app.tasks.reports.generate_daily_reports",
        "schedule": crontab(hour=22, minute=30),  # 22:30
    },
    "report-monthly": {
        "task": "app.tasks.reports.generate_monthly_reports",
        "schedule": crontab(day_of_month=28, hour=23, minute=0),
        # Примечание: для месяцев с 28-31 днями — дополнительная логика
    },
    "monthly-reset": {
        "task": "app.tasks.lifecycle.monthly_reset",
        "schedule": crontab(day_of_month=1, hour=0, minute=5),  # 00:05 1-го числа
    },
}
```
