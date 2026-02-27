# Синхронизация данных с YClients

## Обзор

YClients — основной источник данных для всех расчётов. Система использует три механизма синхронизации для обеспечения надёжности и актуальности данных.

## Механизмы синхронизации

### 1. Webhooks (основной канал, real-time)

YClients отправляет HTTP POST запросы при событиях:
- Создание визита (record.created)
- Изменение визита (record.updated)
- Завершение визита (record.completed)
- Отмена визита (record.cancelled)

**Обработка webhook:**
1. Валидация подписи (HMAC)
2. Парсинг события
3. Маппинг данных YClients → локальные модели
4. Сохранение/обновление в PostgreSQL
5. Триггер пересчёта рейтинга для затронутого филиала
6. Push обновления через WebSocket

**Endpoint:** `POST /api/webhooks/yclients`

### 2. Polling (fallback, каждые 10 минут)

Фоновая задача Celery запрашивает данные из YClients API за последние 20 минут.

**Алгоритм:**
1. Запрос GET /records с фильтром по дате (последние 20 минут)
2. Сравнение с локальной базой
3. Если найдены новые/изменённые записи — обновление
4. Пересчёт рейтингов при изменениях

**Зачем:** Webhooks YClients не гарантируют 100% доставку. Polling — страховка.

### 3. Полная синхронизация (ежедневно в 04:00)

Celery Beat задача: полная сверка всех визитов за предыдущий день.

**Алгоритм:**
1. Запрос всех записей за вчера из YClients API
2. Сравнение с локальной базой
3. Добавление пропущенных, корректировка расхождений
4. Финальный пересчёт рейтингов и ПВР за предыдущий день
5. Генерация итоговых отчётов (если ещё не сгенерированы)

## Маппинг данных YClients → Barber Kombat

### Визит (Record → Visit)

```python
# YClients record → наша модель Visit
mapping = {
    "id": "yclients_record_id",
    "company_id": "→ branch (по yclients_company_id)",
    "staff_id": "→ barber (по yclients_staff_id)",
    "client": {
        "id": "→ client (по yclients_client_id)",
        "phone": "client.phone",
        "name": "client.name",
    },
    "date": "date",
    "services": "→ services (JSONB), вычисляется extras_count",
    "goods_transactions": "→ products (JSONB), вычисляется products_count",
    "cost": "revenue (общая сумма в копейках)",
    "paid_full": "payment_type",
    "visit_attendance": "status (1=completed, 2=cancelled, -1=no_show)",
}
```

### Определение дополнительных услуг (extras)

Допы определяются по списку из `rating_configs.extra_services`. При синхронизации визита каждая услуга проверяется: если её название содержится в списке допов — она считается дополнительной.

```python
# Пример
extra_services = ["воск", "камуфляж головы", "камуфляж бороды", "массаж", "премиум помывка"]

# При обработке визита
for service in visit.services:
    if service["title"].lower() in [e.lower() for e in extra_services]:
        extras_count += 1
```

### Определение чистой выручки (для ПВР)

```python
# Чистая выручка = только услуги, оплаченные деньгами
clean_revenue = sum(
    service.price
    for service in visit.services
    if visit.payment_type in ["card", "cash", "qr"]
    # НЕ считаем: certificate, cashback
)
# Товары НЕ входят в чистую выручку (по умолчанию, конфигурируемо)
```

## YClients API Endpoints

Основные endpoints, которые использует система:

| Endpoint | Метод | Назначение |
|----------|-------|-----------|
| /api/v1/records/{company_id} | GET | Список визитов с фильтрами |
| /api/v1/record/{company_id}/{record_id} | GET | Детали визита |
| /api/v1/staff/{company_id} | GET | Список сотрудников |
| /api/v1/services/{company_id} | GET | Список услуг |
| /api/v1/goods/{company_id} | GET | Список товаров |
| /api/v1/clients/{company_id} | GET | Список клиентов |
| /api/v1/client/{company_id}/{client_id} | GET | Детали клиента |

**Авторизация:** Header `Authorization: Bearer {token}` + `Accept: application/vnd.yclients.v2+json`

## Обработка ошибок

### YClients API недоступен
- Retry с экспоненциальным backoff (3 попытки: 10s, 30s, 90s)
- Если все попытки неудачны — логирование ошибки, следующая попытка через 10 минут (polling)
- Алерт администратору если API недоступен > 30 минут

### Некорректные данные
- Валидация через Pydantic до записи в БД
- Невалидные записи логируются, не прерывают синхронизацию
- Отчёт о невалидных записях в логах

### Дубликаты
- Уникальный ключ yclients_record_id предотвращает дубликаты
- UPSERT (INSERT ... ON CONFLICT UPDATE) для безопасного обновления

## Первоначальная загрузка данных

При подключении нового клиента выполняется полная загрузка:
1. Все сотрудники → users
2. Все услуги → для маппинга допов
3. Все визиты за текущий месяц → visits
4. Все клиенты из визитов → clients
5. Расчёт рейтингов за каждый день текущего месяца
6. Расчёт ПВР (накопительная выручка)

Команда: `python -m app.cli sync-initial --org-id=XXX`
