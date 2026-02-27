# Модуль планирования и контроля

## Назначение

Управление планами по выручке на уровне сети и филиалов. Автоматический расчёт выполнения и прогнозирование.

## Механика

### Установка плана

Владелец устанавливает план для каждого филиала на месяц через Mini App (Настройки → Планы).

```python
# POST /api/plans/{branch_id}
{
    "month": "2024-10-01",
    "target_amount": 240000000  # 2 400 000₽ в копейках
}
```

### Автоматический расчёт

При каждом обновлении данных от Sync Service:

```python
def update_plan(branch_id: UUID, month: date):
    plan = get_plan(branch_id, month)
    if not plan:
        return
    
    # Текущая накопительная выручка
    current = sum(
        visits.revenue
        WHERE branch_id = branch_id
        AND date >= first_day(month)
        AND date <= today()
        AND status = 'completed'
    )
    
    plan.current_amount = current
    plan.percentage = (current / plan.target_amount) * 100
    
    # Прогноз на конец месяца (линейная экстраполяция)
    days_passed = (today() - first_day(month)).days + 1
    days_in_month = last_day(month).day
    
    if days_passed > 0:
        daily_avg = current / days_passed
        plan.forecast_amount = daily_avg * days_in_month
    
    save(plan)
```

### Расчёт необходимой ежедневной выручки

```python
remaining = plan.target_amount - plan.current_amount
days_left = (last_day(month) - today()).days
# Примерно 60% дней — рабочие смены
working_days_left = int(days_left * 0.6)

if working_days_left > 0:
    required_daily = remaining / working_days_left
```

### Уведомление при отклонении

Если на текущую дату выполнение плана отстаёт более чем на 15% от ожидаемого:

```python
expected_percentage = (days_passed / days_in_month) * 100
actual_percentage = plan.percentage

if actual_percentage < expected_percentage - 15:
    send_notification(
        type="plan_warning",
        branch_id=branch_id,
        message=f"Филиал {branch.name}: выполнение плана {actual_percentage:.0f}%, ожидалось {expected_percentage:.0f}%"
    )
```

## Отображение в Mini App

### Для барбера (в экране Комбат)

```
📋 План октября: 2 400 000₽
[====================--------] 77%
Текущая: 1 850 000₽
Нужно: ~36 700₽/смену
```

### Для владельца (дашборд)

Карточка филиала:
```
8 марта
85 000₽ сегодня
[████████░░] 77% плана
3/4 мастеров
```

Детализация при клике:
```
План: 2 400 000₽
Факт: 1 850 000₽ (77%)
Прогноз: 2 350 000₽ (98%)
Осталось: 550 000₽
Нужно/смену: 36 700₽
```
