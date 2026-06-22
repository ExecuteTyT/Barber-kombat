"""Telegram bot for sending formatted notifications and reports.

Uses python-telegram-bot (async) to send MarkdownV2-formatted messages
with inline keyboard buttons linking to the Mini App.
"""

import re

import structlog
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

from app.config import settings

logger = structlog.stdlib.get_logger()

# Medal emojis for rankings
_MEDALS = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}  # 🥇🥈🥉


def _escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2.

    Characters that need escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))


def _format_money(kopecks: int) -> str:
    """Format kopeck amount to human-readable rubles string.

    Examples: 1_350_000 → '13 500 ₽', 80_000_000 → '800 000 ₽'
    """
    rubles = kopecks // 100
    # Format with space as thousands separator
    formatted = f"{rubles:,}".replace(",", " ")
    return f"{formatted} \u20bd"


def _format_money_escaped(kopecks: int) -> str:
    """Format money and escape for MarkdownV2."""
    return _escape_md(_format_money(kopecks))


_RU_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _ru_date(iso: str) -> str:
    """ISO date -> e.g. 21 June (russian). Falls back to raw on parse error."""
    try:
        _, m, d = iso.split("-")
        return f"{int(d)} {_RU_MONTHS[int(m) - 1]}"
    except (ValueError, IndexError):
        return iso


_RU_MONTHS_NOM = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)


def _ru_month(iso: str) -> str:
    """'2026-02-01' -> 'Февраль 2026'. Falls back to raw on parse error."""
    try:
        parts = iso.split("-")
        return f"{_RU_MONTHS_NOM[int(parts[1]) - 1]} {parts[0]}"
    except (ValueError, IndexError):
        return iso


def _ru_datetime(iso: str) -> str:
    """'2026-06-21T14:30:00' -> '21 июня, 14:30'. Falls back to raw on error."""
    try:
        date_part, _, time_part = iso.partition("T")
        hhmm = ":".join(time_part.split(":")[:2]) if time_part else ""
        rd = _ru_date(date_part)
        return f"{rd}, {hhmm}" if hhmm else rd
    except (ValueError, IndexError):
        return iso


def _miniapp_url(path: str = "") -> str:
    """Build Mini App deep link URL."""
    base = settings.telegram_mini_app_url.rstrip("/")
    if path:
        return f"{base}?startapp={path}"
    return base


def _detail_keyboard(
    path: str, label: str = "\u041f\u043e\u0434\u0440\u043e\u0431\u043d\u0435\u0435 \u2192"
) -> InlineKeyboardMarkup:
    """Create an inline keyboard with a single 'Подробнее →' button."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=_miniapp_url(path))]])


def _detail_keyboard_webapp(path: str, label: str = "Подробнее →") -> InlineKeyboardMarkup:
    """Inline button that opens the Mini App INSIDE Telegram (authenticated).

    Uses a web_app button, which Telegram allows only in private chats — so this
    is for the owner's private-DM reports (revenue, day-to-day). Group messages
    (kombat/PVR) keep the plain url button via ``_detail_keyboard``.
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, web_app=WebAppInfo(url=_miniapp_url(path)))]]
    )


# ------------------------------------------------------------------
# Message formatters
# ------------------------------------------------------------------


def format_kombat_report(report_data: dict, branch_data: dict) -> str:
    """Format daily Kombat report for a branch."""
    date_str = _escape_md(_ru_date(report_data["date"]))
    standings = branch_data.get("standings", [])

    lines = [
        f"🏆 *MAKON · Рейтинг дня* · {date_str}",
        "",
    ]

    if standings:
        winner = standings[0]
        lines.append(f"*Победитель дня: {_escape_md(winner['name'])}* 🥇")
        lines.append("")
        lines.append("*Рейтинг:*")
        for entry in standings[:10]:
            rank = entry["rank"]
            medal = _MEDALS.get(rank, f"{rank}\\.")
            name = _escape_md(entry["name"])
            score = _escape_md(f"{entry['total_score']:.1f}")
            lines.append(f"{medal} {name} · *{score}*")
    else:
        lines.append("_Нет данных за день_")

    return "\n".join(lines)


def format_kombat_monthly(report_data: dict, branch_data: dict) -> str:
    """Format monthly Kombat summary for a branch."""
    month = _escape_md(_ru_month(report_data.get("month", "")))
    standings = branch_data.get("standings", [])

    lines = [
        "🏆 *MAKON · Итоги месяца*",
        f"📅 {month}",
        "",
    ]

    if standings:
        champion = standings[0]
        lines.append(f"👑 *Чемпион: {_escape_md(champion['name'])}*")
        lines.append("")
        for entry in standings[:10]:
            rank = entry["rank"]
            medal = _MEDALS.get(rank, f"{rank}\\.")
            name = _escape_md(entry["name"])
            avg = _escape_md(f"{entry['avg_score']:.1f}")
            wins = _escape_md(str(entry.get("wins", 0)))
            days = _escape_md(str(entry.get("days_worked", 0)))
            lines.append(f"{medal} {name} · *{avg}* \\({wins} побед, {days} дн\\.\\)")
    else:
        lines.append("_Нет данных_")

    return "\n".join(lines)


def format_revenue_report(report_data: dict) -> str:
    """Format daily revenue report for the owner (MarkdownV2)."""
    e = _escape_md
    date_str = e(_ru_date(report_data["date"]))
    branches = report_data.get("branches", [])

    lines = [f"💰 *Итоги дня* · {date_str}", ""]

    for b in branches:
        name = e(b["name"])
        today = _format_money_escaped(b["revenue_today"])
        avg = _format_money_escaped(b.get("avg_check_today", 0))
        clients = e(str(b.get("clients_today", 0)))
        new = e(str(b.get("new_clients_today", 0)))
        mtd = _format_money_escaped(b["revenue_mtd"])
        forecast = _format_money_escaped(b.get("forecast_month", 0))

        lines.append(f"📍 *{name}*")
        lines.append(f"  Выручка за день: *{today}*")
        lines.append(f"  Средний чек: {avg} · клиентов: {clients} \\(новые: {new}\\)")

        top = b.get("top_barber")
        if top and top.get("revenue"):
            lines.append(f"  Топ дня: {e(top['name'])} · {_format_money_escaped(top['revenue'])}")

        if b.get("plan_target", 0) > 0:
            pct = e(f"{b['plan_percentage']:.0f}%")
            lines.append(f"  За месяц: {mtd} · {pct} плана · прогноз \\~{forecast}")
        else:
            lines.append(f"  За месяц: {mtd} · прогноз \\~{forecast}")
        lines.append("")

    net_today = _format_money_escaped(report_data.get("network_total_today", 0))
    net_avg = _format_money_escaped(report_data.get("network_avg_check", 0))
    net_clients = e(str(report_data.get("network_clients_today", 0)))
    net_mtd = _format_money_escaped(report_data.get("network_total_mtd", 0))
    net_forecast = _format_money_escaped(report_data.get("network_forecast_month", 0))

    lines.append(
        f"🌐 *Сеть за день:* {net_today} · средний чек: {net_avg} · клиентов: {net_clients}"
    )
    lines.append(f"  За месяц: {net_mtd} · прогноз \\~{net_forecast}")

    return "\n".join(lines)


def format_day_to_day(report_data: dict) -> str:
    """Format day-to-day comparison report (same period across 3 months)."""
    period_iso = report_data.get("period_end", "")
    period_end = _escape_md(_ru_date(period_iso))
    try:
        day_num = int(period_iso.split("-")[2])
    except (ValueError, IndexError):
        day_num = 0

    def _at_day(month: dict) -> int:
        cum = month.get("daily_cumulative") or []
        for d in cum:
            if d.get("day") == day_num:
                return d["amount"]
        return cum[-1]["amount"] if cum else 0

    comparison = report_data.get("comparison", {})
    current = report_data.get("current_month", {})
    prev = report_data.get("prev_month", {})
    prev_prev = report_data.get("prev_prev_month", {})

    lines = [
        f"📈 *Динамика выручки* · {period_end}",
        "_Сравниваем с тем же периодом прошлых месяцев_",
        "",
        f"📅 *{_escape_md(current.get('name', ''))}:* {_format_money_escaped(_at_day(current))}",
        f"📅 {_escape_md(prev.get('name', ''))}: {_format_money_escaped(_at_day(prev))}",
        f"📅 {_escape_md(prev_prev.get('name', ''))}: {_format_money_escaped(_at_day(prev_prev))}",
        "",
        "📊 *Темп к прошлым месяцам:*",
        f"  {_escape_md(prev.get('name', ''))}: *{_escape_md(comparison.get('vs_prev', '0.0%'))}*",
        f"  {_escape_md(prev_prev.get('name', ''))}: *{_escape_md(comparison.get('vs_prev_prev', '0.0%'))}*",
    ]

    return "\n".join(lines)


def format_pvr_bell(barber_name: str, threshold: int, bonus: int) -> str:
    """Format PVR threshold crossing notification."""
    name = _escape_md(barber_name)
    threshold_str = _format_money_escaped(threshold)
    bonus_str = _format_money_escaped(bonus)

    lines = [
        "🔔🔔🔔",
        "",
        f"*{name}* заработал за месяц *{threshold_str}*\\!",
        f"Премия: *\\+{bonus_str}* 🎉",
        "",
        "Так держать\\! 💪",
    ]

    return "\n".join(lines)


def format_review_request(barber_name: str, review_url: str) -> str:
    """Format review request message for WhatsApp / Telegram.

    Plain text (no MarkdownV2) — WhatsApp doesn't support it.
    """
    return (
        f"Здравствуйте! Спасибо, что посетили нашу барбершоп.\n"
        f"Ваш мастер сегодня — {barber_name}.\n\n"
        f"Будем благодарны за обратную связь — это займёт меньше минуты:\n"
        f"{review_url}\n\n"
        f"Спасибо! 💈"
    )


def format_negative_review(
    branch_name: str,
    barber_name: str,
    client_name: str | None,
    rating: int,
    comment: str | None,
    created_at: str,
) -> str:
    """Format negative review alert."""
    stars = "⭐" * rating
    rating_str = _escape_md(f"({rating}/5)")

    lines = [
        "⚠️ *Негативный отзыв*",
        "",
        f"📍 Филиал: {_escape_md(branch_name)}",
        f"👤 Мастер: {_escape_md(barber_name)}",
    ]

    if client_name:
        lines.append(f"📞 Клиент: {_escape_md(client_name)}")

    lines.append(f"⭐ Оценка: {stars} {rating_str}")

    if comment:
        lines.append(f"💬 _{_escape_md(comment)}_")

    lines.append("")
    lines.append(f"🕐 {_escape_md(_ru_datetime(created_at))}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Telegram sender
# ------------------------------------------------------------------


class TelegramBot:
    """Wrapper around python-telegram-bot for sending formatted messages."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token
        self._bot: Bot | None = None

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            # Route through a proxy when configured (api.telegram.org is blocked
            # on some hosts, e.g. RU). Without it, default direct connection.
            request = (
                HTTPXRequest(proxy=settings.telegram_proxy)
                if settings.telegram_proxy
                else None
            )
            self._bot = Bot(token=self.token, request=request)
        return self._bot

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> bool:
        """Send a MarkdownV2 message to a Telegram chat.

        Returns True if sent successfully, False otherwise.
        """
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup,
            )
            await logger.ainfo(
                "Telegram message sent",
                chat_id=chat_id,
            )
            return True
        except Exception:
            await logger.aexception(
                "Failed to send Telegram message",
                chat_id=chat_id,
            )
            return False

    # --- High-level send methods ---

    async def send_kombat_report(
        self,
        chat_id: int,
        report_data: dict,
        branch_data: dict,
        branch_id: str,
    ) -> bool:
        """Send daily Kombat report to a branch group."""
        text = format_kombat_report(report_data, branch_data)
        keyboard = _detail_keyboard(f"kombat_{branch_id}")
        return await self.send_message(chat_id, text, keyboard)

    async def send_kombat_monthly(
        self,
        chat_id: int,
        report_data: dict,
        branch_data: dict,
        branch_id: str,
    ) -> bool:
        """Send monthly Kombat summary to a branch group."""
        text = format_kombat_monthly(report_data, branch_data)
        keyboard = _detail_keyboard(f"kombat_{branch_id}")
        return await self.send_message(chat_id, text, keyboard)

    async def send_revenue_report(
        self,
        chat_id: int,
        report_data: dict,
    ) -> bool:
        """Send daily revenue report to the owner."""
        text = format_revenue_report(report_data)
        keyboard = _detail_keyboard_webapp("revenue")
        return await self.send_message(chat_id, text, keyboard)

    async def send_day_to_day(
        self,
        chat_id: int,
        report_data: dict,
    ) -> bool:
        """Send day-to-day comparison report to the owner."""
        text = format_day_to_day(report_data)
        keyboard = _detail_keyboard_webapp("day_to_day")
        return await self.send_message(chat_id, text, keyboard)

    async def send_pvr_bell(
        self,
        chat_id: int,
        barber_name: str,
        threshold: int,
        bonus: int,
    ) -> bool:
        """Send PVR threshold bell notification to a branch group."""
        text = format_pvr_bell(barber_name, threshold, bonus)
        return await self.send_message(chat_id, text)

    async def send_plain_message(self, chat_id: int, text: str) -> bool:
        """Send a plain-text message (no MarkdownV2 parsing)."""
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            await logger.ainfo("Telegram plain message sent", chat_id=chat_id)
            return True
        except Exception:
            await logger.aexception("Failed to send Telegram plain message", chat_id=chat_id)
            return False

    async def send_negative_review(
        self,
        chat_id: int,
        branch_name: str,
        barber_name: str,
        client_name: str | None,
        rating: int,
        comment: str | None,
        created_at: str,
        review_id: str,
    ) -> bool:
        """Send negative review alert to the manager/chef."""
        text = format_negative_review(
            branch_name=branch_name,
            barber_name=barber_name,
            client_name=client_name,
            rating=rating,
            comment=comment,
            created_at=created_at,
        )
        keyboard = _detail_keyboard(
            f"review_{review_id}",
            label="\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c \u2192",
        )
        return await self.send_message(chat_id, text, keyboard)

    async def send_review_request(self, chat_id: int, barber_name: str, review_url: str) -> bool:
        """Send review request to client via Telegram (fallback if WhatsApp fails)."""
        text = format_review_request(barber_name, review_url)
        return await self.send_plain_message(chat_id, text)
