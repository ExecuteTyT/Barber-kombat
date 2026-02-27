"""Telegram bot for sending formatted notifications and reports.

Uses python-telegram-bot (async) to send MarkdownV2-formatted messages
with inline keyboard buttons linking to the Mini App.
"""

import re
import uuid

import structlog
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

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


def _miniapp_url(path: str = "") -> str:
    """Build Mini App deep link URL."""
    base = settings.telegram_mini_app_url.rstrip("/")
    if path:
        return f"{base}?startapp={path}"
    return base


def _detail_keyboard(path: str, label: str = "\u041f\u043e\u0434\u0440\u043e\u0431\u043d\u0435\u0435 \u2192") -> InlineKeyboardMarkup:
    """Create an inline keyboard with a single 'Подробнее →' button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, url=_miniapp_url(path))]
    ])


# ------------------------------------------------------------------
# Message formatters
# ------------------------------------------------------------------


def format_kombat_report(report_data: dict, branch_data: dict) -> str:
    """Format daily Kombat report for a branch.

    Args:
        report_data: Full kombat_daily report dict.
        branch_data: Single branch entry from report_data["branches"].
    """
    date_str = _escape_md(report_data["date"])
    standings = branch_data.get("standings", [])

    lines = [
        f"\U0001f3c6 *BARBER KOMBAT* \u2014 {date_str}",
        "",
    ]

    if standings:
        winner = standings[0]
        lines.append(
            f"*\u041f\u043e\u0431\u0435\u0434\u0438\u0442\u0435\u043b\u044c \u0434\u043d\u044f: "
            f"{_escape_md(winner['name'])}* \U0001f947"
        )
        lines.append("")
        lines.append("*\u0420\u0435\u0439\u0442\u0438\u043d\u0433:*")

        for entry in standings[:10]:
            rank = entry["rank"]
            medal = _MEDALS.get(rank, f"{rank}\\.")
            name = _escape_md(entry["name"])
            score = _escape_md(f"{entry['total_score']:.1f}")
            lines.append(f"{medal} {name} \u2014 *{score}*")
    else:
        lines.append("_\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u0437\u0430 \u0434\u0435\u043d\u044c_")

    return "\n".join(lines)


def format_kombat_monthly(report_data: dict, branch_data: dict) -> str:
    """Format monthly Kombat summary for a branch."""
    month = _escape_md(report_data.get("month", ""))
    standings = branch_data.get("standings", [])

    lines = [
        f"\U0001f3c6 *BARBER KOMBAT \u2014 \u0418\u0442\u043e\u0433\u0438 \u043c\u0435\u0441\u044f\u0446\u0430*",
        f"\U0001f4c5 {month}",
        "",
    ]

    if standings:
        champion = standings[0]
        lines.append(
            f"\U0001f451 *\u0427\u0435\u043c\u043f\u0438\u043e\u043d: "
            f"{_escape_md(champion['name'])}*"
        )
        lines.append("")

        for entry in standings[:10]:
            rank = entry["rank"]
            medal = _MEDALS.get(rank, f"{rank}\\.")
            name = _escape_md(entry["name"])
            avg = _escape_md(f"{entry['avg_score']:.1f}")
            wins = entry.get("wins", 0)
            days = entry.get("days_worked", 0)
            lines.append(
                f"{medal} {name} \u2014 *{avg}* "
                f"\\({_escape_md(str(wins))} \u043f\u043e\u0431\\. / "
                f"{_escape_md(str(days))} \u0434\u043d\\.\\)"
            )
    else:
        lines.append("_\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445_")

    return "\n".join(lines)


def format_revenue_report(report_data: dict) -> str:
    """Format daily revenue report for the owner."""
    date_str = _escape_md(report_data["date"])
    branches = report_data.get("branches", [])

    lines = [
        f"\U0001f4b0 *\u0412\u044b\u0440\u0443\u0447\u043a\u0430 \u0437\u0430 \u0434\u0435\u043d\u044c* \u2014 {date_str}",
        "",
    ]

    for b in branches:
        name = _escape_md(b["name"])
        today = _format_money_escaped(b["revenue_today"])
        mtd = _format_money_escaped(b["revenue_mtd"])
        pct = _escape_md(f"{b['plan_percentage']:.1f}%")
        barbers = _escape_md(f"{b['barbers_in_shift']}/{b['barbers_total']}")

        lines.append(f"\U0001f4cd *{name}*")
        lines.append(f"  \u0421\u0435\u0433\u043e\u0434\u043d\u044f: *{today}*")
        lines.append(f"  \u041c\u0435\u0441\u044f\u0446: {mtd} \\({pct} \u043f\u043b\u0430\u043d\u0430\\)")
        lines.append(f"  \u0411\u0430\u0440\u0431\u0435\u0440\u044b: {barbers}")
        lines.append("")

    network_today = _format_money_escaped(report_data.get("network_total_today", 0))
    network_mtd = _format_money_escaped(report_data.get("network_total_mtd", 0))
    lines.append(f"\U0001f310 *\u0421\u0435\u0442\u044c:* {network_today} \\(\u043c\u0435\u0441\u044f\u0446: {network_mtd}\\)")

    return "\n".join(lines)


def format_day_to_day(report_data: dict) -> str:
    """Format day-to-day comparison report."""
    period_end = _escape_md(report_data.get("period_end", ""))
    comparison = report_data.get("comparison", {})
    current = report_data.get("current_month", {})
    prev = report_data.get("prev_month", {})
    prev_prev = report_data.get("prev_prev_month", {})

    # Latest cumulative amounts
    cur_total = current.get("daily_cumulative", [{}])
    cur_amount = cur_total[-1]["amount"] if cur_total else 0
    prev_total = prev.get("daily_cumulative", [{}])
    prev_amount = prev_total[-1]["amount"] if prev_total else 0
    pp_total = prev_prev.get("daily_cumulative", [{}])
    pp_amount = pp_total[-1]["amount"] if pp_total else 0

    lines = [
        f"\U0001f4c8 *Day\\-to\\-Day* \u2014 {period_end}",
        "",
        f"\U0001f4c5 *{_escape_md(current.get('name', ''))}:* "
        f"{_format_money_escaped(cur_amount)}",
        f"\U0001f4c5 *{_escape_md(prev.get('name', ''))}:* "
        f"{_format_money_escaped(prev_amount)}",
        f"\U0001f4c5 *{_escape_md(prev_prev.get('name', ''))}:* "
        f"{_format_money_escaped(pp_amount)}",
        "",
        f"\U0001f4ca \u0421\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u0435:",
        f"  \u0432\u0441\\. \u043f\u0440\u043e\u0448\u043b\\. \u043c\u0435\u0441\\.: *{_escape_md(comparison.get('vs_prev', '0.0%'))}*",
        f"  \u0432\u0441\\. \u043f\u043e\u0437\u0430\u043f\u0440\u043e\u0448\u043b\\.: *{_escape_md(comparison.get('vs_prev_prev', '0.0%'))}*",
    ]

    return "\n".join(lines)


def format_pvr_bell(barber_name: str, threshold: int, bonus: int) -> str:
    """Format PVR threshold crossing notification."""
    name = _escape_md(barber_name)
    threshold_str = _format_money_escaped(threshold)
    bonus_str = _format_money_escaped(bonus)

    lines = [
        "\U0001f514\U0001f514\U0001f514",
        "",
        f"*{name}* \u0441\u0434\u0435\u043b\u0430\u043b \u0432\u044b\u0440\u0443\u0447\u043a\u0443 *{threshold_str}*\\!",
        f"\u041f\u0440\u0435\u043c\u0438\u044f: *\\+{bonus_str}* \U0001f389",
        "",
        "\u0422\u0430\u043a \u0434\u0435\u0440\u0436\u0430\u0442\u044c\\! \U0001f4aa",
    ]

    return "\n".join(lines)


def format_negative_review(
    branch_name: str,
    barber_name: str,
    client_name: str | None,
    rating: int,
    comment: str | None,
    created_at: str,
) -> str:
    """Format negative review alert."""
    stars = "\u2b50" * rating
    rating_str = _escape_md(f"({rating}/5)")

    lines = [
        "\u26a0\ufe0f *\u041d\u0435\u0433\u0430\u0442\u0438\u0432\u043d\u044b\u0439 \u043e\u0442\u0437\u044b\u0432*",
        "",
        f"\U0001f4cd \u0424\u0438\u043b\u0438\u0430\u043b: {_escape_md(branch_name)}",
        f"\U0001f464 \u041c\u0430\u0441\u0442\u0435\u0440: {_escape_md(barber_name)}",
    ]

    if client_name:
        lines.append(f"\U0001f4de \u041a\u043b\u0438\u0435\u043d\u0442: {_escape_md(client_name)}")

    lines.append(f"\u2b50 \u041e\u0446\u0435\u043d\u043a\u0430: {stars} {rating_str}")

    if comment:
        lines.append(f"\U0001f4ac _{_escape_md(comment)}_")

    lines.append("")
    lines.append(f"\U0001f550 {_escape_md(created_at)}")

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
            self._bot = Bot(token=self.token)
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
        keyboard = _detail_keyboard("revenue")
        return await self.send_message(chat_id, text, keyboard)

    async def send_day_to_day(
        self,
        chat_id: int,
        report_data: dict,
    ) -> bool:
        """Send day-to-day comparison report to the owner."""
        text = format_day_to_day(report_data)
        keyboard = _detail_keyboard("day_to_day")
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
