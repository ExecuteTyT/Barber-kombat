# Модуль ПВР (Премия за высокие результаты)

## Назначение

Система удержания топовых сотрудников через дополнительную мотивацию за высокую накопительную выручку за месяц.

## Механика

### Что считается

Накопительная **чистая выручка** барбера с 1-го числа месяца:
- ✅ Выручка за оказанные услуги (стрижки, допы)
- ✅ Оплата наличными, картой, QR
- ❌ Продажа товаров (по умолчанию, конфигурируемо)
- ❌ Оплата сертификатом
- ❌ Кешбэки

### Расчёт

```python
def calculate_pvr(barber_id: UUID, month: date) -> PVRRecord:
    # Собираем все завершённые визиты барбера за месяц
    visits = get_visits(
        barber_id=barber_id,
        date_from=first_day_of_month(month),
        date_to=last_day_of_month(month),
        status="completed",
    )
    
    # Считаем чистую выручку
    clean_revenue = 0
    for visit in visits:
        if visit.payment_type in ("card", "cash", "qr"):
            clean_revenue += visit.services_revenue  # Только услуги, не товары
    
    # Определяем достигнутый порог
    thresholds = get_pvr_config(organization_id).thresholds
    # thresholds отсортированы по убыванию: [800k, 600k, 500k, 400k, 350k, 300k]
    
    current_threshold = None
    bonus = 0
    for t in sorted(thresholds, key=lambda x: x["amount"], reverse=True):
        if clean_revenue >= t["amount"]:
            current_threshold = t["amount"]
            bonus = t["bonus"]
            break
    
    return PVRRecord(
        barber_id=barber_id,
        month=month,
        cumulative_revenue=clean_revenue,
        current_threshold=current_threshold,
        bonus_amount=bonus,
    )
```

### Пороги по умолчанию

| Чистая выручка | Премия |
|---------------|--------|
| 300 000 ₽ | +10 000 ₽ |
| 350 000 ₽ | +15 000 ₽ |
| 400 000 ₽ | +20 000 ₽ |
| 500 000 ₽ | +30 000 ₽ |
| 600 000 ₽ | +40 000 ₽ |
| 800 000 ₽ | +50 000 ₽ |

Пороги конфигурируемые через настройки.
Премия НЕ суммируется — платится по наивысшему достигнутому порогу.

## Колокольчик (уведомление о достижении порога)

### Триггер

При каждом обновлении данных от Sync Service пересчитывается накопительная выручка. Если барбер пересёк новый порог (которого не было ранее) — срабатывает колокольчик.

```python
def check_pvr_threshold(barber_id: UUID, old_record: PVRRecord, new_record: PVRRecord):
    if new_record.current_threshold != old_record.current_threshold:
        if new_record.current_threshold > (old_record.current_threshold or 0):
            send_bell_notification(
                barber_id=barber_id,
                threshold=new_record.current_threshold,
                bonus=new_record.bonus_amount,
            )
```

### Формат уведомления

```
🔔🔔🔔

Вау! Павел сделал выручку 500 000 ₽!
Премия: +30 000 ₽ 🎉

Так держать! 💪
```

### Каналы доставки

1. **Telegram-бот → группа филиала** (публичное признание — все видят)
2. **WebSocket → Mini App** (pop-up уведомление для всех пользователей филиала)

## Отображение в Mini App

### Экран "Мой прогресс" (для барбера)

```
Накопительная выручка: 478 500 ₽

[============================----] 500 000 ₽

До следующего порога: 21 500 ₽

Достигнутые пороги:
✅ 300 000 ₽ — 5 октября
✅ 350 000 ₽ — 9 октября
✅ 400 000 ₽ — 12 октября
⬜ 500 000 ₽ — осталось 21 500 ₽
⬜ 600 000 ₽
⬜ 800 000 ₽

Текущая премия: 20 000 ₽
```

### Экран "Бинго" (для шефа/владельца)

Список всех барберов с накопительной выручкой и индикацией порогов:

```
Филиал "8 марта" — октябрь

Мастер           Выручка     Порог      Премия
Иванов П.   🔔   520 000₽    500к      30 000₽
Петров Л.         478 500₽    400к      20 000₽
Сидоров М.        312 000₽    300к      10 000₽
Козлов А.         285 000₽    —              0₽

В смене: 3 / Всего: 4
```

## Обнуление

1-го числа каждого месяца:
- Создаётся новая запись pvr_records для каждого активного барбера
- cumulative_revenue = 0
- bonus_amount = 0
- Старые записи сохраняются для истории
