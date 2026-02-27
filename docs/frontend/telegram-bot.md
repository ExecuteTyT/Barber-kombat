# Telegram-бот: уведомления и отчёты

## Роль бота

Бот — канал push-уведомлений. Он НЕ является интерфейсом для работы с данными. Бот отправляет краткие сводки и ссылки на Mini App для детализации.

## Типы уведомлений

### По расписанию

| Уведомление | Время | Получатель | Формат |
|-------------|-------|-----------|--------|
| Итоги дня (Kombat) | 22:30 | Группа филиала | Победитель, рейтинг, план, призовой фонд |
| Выручка за день | 22:30 | Личный чат владельца | Выручка по филиалам, итого |
| Day-to-day | 11:00 | Личный чат владельца | Сравнение 3 месяцев |
| Итоги месяца | Последний день, 23:00 | Группа филиала | Чемпион, статистика, призовой фонд |

### По событию

| Уведомление | Триггер | Получатель | Формат |
|-------------|---------|-----------|--------|
| Колокольчик ПВР | Барбер пересёк порог | Группа филиала | Поздравление, сумма, премия |
| Негативный отзыв | Оценка < 4 | Личный чат управляющего/шефа | Клиент, мастер, оценка, комментарий |
| Отклонение от плана | % < ожидаемого - 15% | Личный чат управляющего | Филиал, % отклонения |

## Формат сообщений

Все сообщения используют Telegram MarkdownV2.
Каждое сообщение содержит inline-кнопку "Подробнее →" с deep link на Mini App.

### Пример: Итоги дня

```python
message = f"""
🏆 *BARBER KOMBAT* — {date}

*Победитель дня: {winner_name}* 🥇

*Рейтинг:*
🥇 {barbers[0].name} — *{barbers[0].score}*
🥈 {barbers[1].name} — *{barbers[1].score}*
🥉 {barbers[2].name} — *{barbers[2].score}*

📊 *Зачёт {month_name}:*
{standings_text}

📋 *План:* {plan_pct}% \\({format_money(plan_current)} из {format_money(plan_target)}\\)

💰 *Призовой фонд:*
🥇 {format_money(gold)} 🥈 {format_money(silver)} 🥉 {format_money(bronze)}
"""

keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Подробнее →", url=f"https://t.me/{bot_username}/app?startapp=kombat_{branch_id}")]
])
```

### Пример: Колокольчик ПВР

```python
message = f"""
🔔🔔🔔

*{barber_name}* сделал выручку *{format_money(threshold)}*\\!
Премия: *\\+{format_money(bonus)}* 🎉

Так держать\\! 💪
"""
```

### Пример: Негативный отзыв

```python
message = f"""
⚠️ *Негативный отзыв*

📍 Филиал: {branch_name}
👤 Мастер: {barber_name}
📞 Клиент: {client_name}
⭐ Оценка: {"⭐" * rating} \\({rating}/5\\)
💬 _{comment}_

🕐 {formatted_time}
"""

keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Обработать →", url=f"https://t.me/{bot_username}/app?startapp=review_{review_id}")]
])
```

## Настройка групп

Владелец настраивает в Mini App (Настройки → Уведомления):
- Для каждого филиала: Telegram group chat_id
- Для владельца: личный chat_id
- Для управляющих: личные chat_id
- Какие типы уведомлений включены для каждого получателя

## Техническая реализация

### Библиотека

python-telegram-bot (async) или aiogram 3

### Celery задачи

```python
# Отправка по расписанию
@celery_app.task
def send_daily_kombat_report(branch_id: str):
    report = generate_kombat_report(branch_id)
    chat_id = get_branch_telegram_group(branch_id)
    send_telegram_message(chat_id, report.message, report.keyboard)

# Отправка по событию
@celery_app.task
def send_pvr_bell(branch_id: str, barber_name: str, threshold: int, bonus: int):
    chat_id = get_branch_telegram_group(branch_id)
    message = format_pvr_bell(barber_name, threshold, bonus)
    send_telegram_message(chat_id, message)
```

### Регистрация бота

1. Создать бота через @BotFather
2. Включить Mini App: /newapp в BotFather
3. Настроить webhook: `POST /api/webhooks/telegram`
4. Добавить бота в группы филиалов как администратора
