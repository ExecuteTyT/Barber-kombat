"""Tests for Telegram bot formatters and send logic."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.telegram.bot import (
    TelegramBot,
    _escape_md,
    _format_money,
    _format_money_escaped,
    _miniapp_url,
    format_day_to_day,
    format_kombat_monthly,
    format_kombat_report,
    format_negative_review,
    format_pvr_bell,
    format_revenue_report,
)

# --- Test helpers ---

BRANCH_ID = str(uuid.uuid4())
REVIEW_ID = str(uuid.uuid4())


def _kombat_daily_data(standings=None):
    """Build a minimal kombat_daily report dict."""
    if standings is None:
        standings = [
            {
                "barber_id": str(uuid.uuid4()),
                "name": "Павел",
                "rank": 1,
                "total_score": 95.5,
                "revenue": 1_350_000,
            },
            {
                "barber_id": str(uuid.uuid4()),
                "name": "Иван",
                "rank": 2,
                "total_score": 82.3,
                "revenue": 1_100_000,
            },
            {
                "barber_id": str(uuid.uuid4()),
                "name": "Дмитрий",
                "rank": 3,
                "total_score": 70.1,
                "revenue": 900_000,
            },
        ]
    return {
        "date": "2026-02-22",
        "branches": [
            {
                "branch_id": BRANCH_ID,
                "name": "8 марта",
                "standings": standings,
            }
        ],
    }


def _kombat_monthly_data():
    return {
        "month": "2026-02-01",
        "branches": [
            {
                "branch_id": BRANCH_ID,
                "name": "8 марта",
                "standings": [
                    {
                        "barber_id": str(uuid.uuid4()),
                        "name": "Павел",
                        "rank": 1,
                        "avg_score": 92.5,
                        "wins": 15,
                        "days_worked": 22,
                        "total_revenue": 520_000_000,
                    },
                    {
                        "barber_id": str(uuid.uuid4()),
                        "name": "Иван",
                        "rank": 2,
                        "avg_score": 85.0,
                        "wins": 7,
                        "days_worked": 20,
                        "total_revenue": 400_000_000,
                    },
                ],
            }
        ],
    }


def _revenue_data():
    return {
        "date": "2026-02-22",
        "branches": [
            {
                "branch_id": BRANCH_ID,
                "name": "8 марта",
                "revenue_today": 850_000,
                "revenue_mtd": 18_500_000,
                "plan_target": 24_000_000,
                "plan_percentage": 77.1,
                "barbers_in_shift": 8,
                "barbers_total": 10,
            }
        ],
        "network_total_today": 2_530_000,
        "network_total_mtd": 55_000_000,
    }


def _day_to_day_data():
    return {
        "branch_id": None,
        "period_end": "2026-02-22",
        "current_month": {
            "name": "Февраль 2026",
            "daily_cumulative": [
                {"day": 1, "amount": 850_000},
                {"day": 22, "amount": 18_500_000},
            ],
        },
        "prev_month": {
            "name": "Январь 2026",
            "daily_cumulative": [
                {"day": 1, "amount": 700_000},
                {"day": 22, "amount": 16_200_000},
            ],
        },
        "prev_prev_month": {
            "name": "Декабрь 2025",
            "daily_cumulative": [
                {"day": 1, "amount": 900_000},
                {"day": 22, "amount": 19_000_000},
            ],
        },
        "comparison": {
            "vs_prev": "+14.2%",
            "vs_prev_prev": "-2.6%",
        },
    }


# ------------------------------------------------------------------
# Tests: Utility functions
# ------------------------------------------------------------------


class TestEscapeMd:
    def test_escapes_special_chars(self):
        assert _escape_md("hello_world") == "hello\\_world"
        assert _escape_md("1.5") == "1\\.5"
        assert _escape_md("(test)") == "\\(test\\)"

    def test_plain_text_unchanged(self):
        assert _escape_md("hello") == "hello"
        assert _escape_md("Павел") == "Павел"

    def test_multiple_special_chars(self):
        result = _escape_md("a_b*c[d]e")
        assert result == "a\\_b\\*c\\[d\\]e"

    def test_numbers_unchanged(self):
        assert _escape_md("12345") == "12345"


class TestFormatMoney:
    def test_simple_amount(self):
        assert _format_money(1_350_000) == "13 500 \u20bd"

    def test_large_amount(self):
        assert _format_money(80_000_000) == "800 000 \u20bd"

    def test_zero(self):
        assert _format_money(0) == "0 \u20bd"

    def test_small_amount(self):
        assert _format_money(100) == "1 \u20bd"

    def test_escaped_version(self):
        result = _format_money_escaped(1_350_000)
        assert "13 500" in result
        assert "\u20bd" in result


class TestMiniAppUrl:
    @patch("app.integrations.telegram.bot.settings")
    def test_url_with_path(self, mock_settings):
        mock_settings.telegram_mini_app_url = "https://t.me/bot/app"
        assert _miniapp_url("kombat_123") == "https://t.me/bot/app?startapp=kombat_123"

    @patch("app.integrations.telegram.bot.settings")
    def test_url_without_path(self, mock_settings):
        mock_settings.telegram_mini_app_url = "https://t.me/bot/app"
        assert _miniapp_url() == "https://t.me/bot/app"

    @patch("app.integrations.telegram.bot.settings")
    def test_trailing_slash_stripped(self, mock_settings):
        mock_settings.telegram_mini_app_url = "https://t.me/bot/app/"
        assert _miniapp_url("test") == "https://t.me/bot/app?startapp=test"


# ------------------------------------------------------------------
# Tests: Message formatters
# ------------------------------------------------------------------


class TestFormatKombatReport:
    def test_contains_winner(self):
        data = _kombat_daily_data()
        branch = data["branches"][0]
        text = format_kombat_report(data, branch)

        assert "MAKON" in text
        assert "2026\\-02\\-22" in text
        assert "Павел" in text

    def test_contains_all_barbers(self):
        data = _kombat_daily_data()
        branch = data["branches"][0]
        text = format_kombat_report(data, branch)

        assert "Павел" in text
        assert "Иван" in text
        assert "Дмитрий" in text

    def test_contains_scores(self):
        data = _kombat_daily_data()
        branch = data["branches"][0]
        text = format_kombat_report(data, branch)

        assert "95\\.5" in text
        assert "82\\.3" in text

    def test_empty_standings(self):
        data = _kombat_daily_data(standings=[])
        branch = data["branches"][0]
        text = format_kombat_report(data, branch)

        assert "MAKON" in text
        # Should show "no data" message in Russian
        assert "\u043d\u0435\u0442" in text.lower() or "\u041d\u0435\u0442" in text


class TestFormatKombatMonthly:
    def test_contains_champion(self):
        data = _kombat_monthly_data()
        branch = data["branches"][0]
        text = format_kombat_monthly(data, branch)

        assert "\u0427\u0435\u043c\u043f\u0438\u043e\u043d" in text
        assert "Павел" in text

    def test_contains_stats(self):
        data = _kombat_monthly_data()
        branch = data["branches"][0]
        text = format_kombat_monthly(data, branch)

        assert "92\\.5" in text
        assert "15" in text  # wins


class TestFormatRevenueReport:
    def test_contains_branch_data(self):
        data = _revenue_data()
        text = format_revenue_report(data)

        assert "8 марта" in text
        assert "77\\.1" in text  # plan percentage

    def test_contains_network_totals(self):
        data = _revenue_data()
        text = format_revenue_report(data)

        assert "\u0421\u0435\u0442\u044c" in text

    def test_contains_money_amounts(self):
        data = _revenue_data()
        text = format_revenue_report(data)

        assert "8 500" in text  # revenue_today: 850_000 kopecks = 8 500 rubles


class TestFormatDayToDay:
    def test_contains_comparison(self):
        data = _day_to_day_data()
        text = format_day_to_day(data)

        assert "Day\\-to\\-Day" in text
        assert "14\\.2" in text or "+14\\.2" in text
        assert "2\\.6" in text or "-2\\.6" in text

    def test_contains_month_names(self):
        data = _day_to_day_data()
        text = format_day_to_day(data)

        assert "Февраль" in text or "\u0424\u0435\u0432\u0440\u0430\u043b\u044c" in text
        assert "Январь" in text or "\u042f\u043d\u0432\u0430\u0440\u044c" in text


class TestFormatPvrBell:
    def test_contains_barber_and_amounts(self):
        text = format_pvr_bell("Павел", 50_000_000, 3_000_000)

        assert "Павел" in text
        assert "500 000" in text  # threshold in rubles
        assert "30 000" in text  # bonus in rubles
        assert "\U0001f514" in text  # bell emoji

    def test_contains_encouragement(self):
        text = format_pvr_bell("Иван", 30_000_000, 1_000_000)

        assert "\u0422\u0430\u043a \u0434\u0435\u0440\u0436\u0430\u0442\u044c" in text


class TestFormatNegativeReview:
    def test_contains_all_fields(self):
        text = format_negative_review(
            branch_name="8 марта",
            barber_name="Павел",
            client_name="Иван",
            rating=2,
            comment="Плохая стрижка",
            created_at="2026-02-22 15:30",
        )

        assert (
            "\u041d\u0435\u0433\u0430\u0442\u0438\u0432\u043d\u044b\u0439 \u043e\u0442\u0437\u044b\u0432"
            in text
        )
        assert "8 марта" in text
        assert "Павел" in text
        assert "Иван" in text
        assert "\u2b50\u2b50" in text  # 2 stars
        assert "Плохая стрижка" in text

    def test_without_client_name(self):
        text = format_negative_review(
            branch_name="Центр",
            barber_name="Дмитрий",
            client_name=None,
            rating=1,
            comment=None,
            created_at="2026-02-22 10:00",
        )

        assert "Дмитрий" in text
        assert "\u041a\u043b\u0438\u0435\u043d\u0442" not in text

    def test_without_comment(self):
        text = format_negative_review(
            branch_name="Центр",
            barber_name="Дмитрий",
            client_name="Анна",
            rating=3,
            comment=None,
            created_at="2026-02-22 10:00",
        )

        assert "\u2b50\u2b50\u2b50" in text  # 3 stars
        assert "\U0001f4ac" not in text  # no comment icon


# ------------------------------------------------------------------
# Tests: TelegramBot send logic
# ------------------------------------------------------------------


class TestTelegramBotSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        bot = TelegramBot(token="test-token")
        mock_tg_bot = AsyncMock()
        bot._bot = mock_tg_bot

        result = await bot.send_message(chat_id=-100123, text="hello")

        assert result is True
        mock_tg_bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        bot = TelegramBot(token="test-token")
        mock_tg_bot = AsyncMock()
        mock_tg_bot.send_message.side_effect = Exception("Network error")
        bot._bot = mock_tg_bot

        result = await bot.send_message(chat_id=-100123, text="hello")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_with_reply_markup(self):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        bot = TelegramBot(token="test-token")
        mock_tg_bot = AsyncMock()
        bot._bot = mock_tg_bot

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Test", url="https://example.com")]])
        result = await bot.send_message(chat_id=-100123, text="hello", reply_markup=kb)

        assert result is True
        call_kwargs = mock_tg_bot.send_message.call_args.kwargs
        assert call_kwargs["reply_markup"] is kb


class TestTelegramBotHighLevelSend:
    @pytest.mark.asyncio
    async def test_send_kombat_report(self):
        bot = TelegramBot(token="test-token")
        bot.send_message = AsyncMock(return_value=True)

        data = _kombat_daily_data()
        branch = data["branches"][0]
        result = await bot.send_kombat_report(
            chat_id=-100123,
            report_data=data,
            branch_data=branch,
            branch_id=BRANCH_ID,
        )

        assert result is True
        bot.send_message.assert_awaited_once()
        # send_message is called with positional args: (chat_id, text, keyboard)
        args = bot.send_message.call_args.args
        assert args[0] == -100123
        assert "BARBER KOMBAT" in args[1]
        assert args[2] is not None  # reply_markup

    @pytest.mark.asyncio
    async def test_send_pvr_bell(self):
        bot = TelegramBot(token="test-token")
        bot.send_message = AsyncMock(return_value=True)

        result = await bot.send_pvr_bell(
            chat_id=-100123,
            barber_name="Павел",
            threshold=50_000_000,
            bonus=3_000_000,
        )

        assert result is True
        args = bot.send_message.call_args.args
        assert "Павел" in args[1]

    @pytest.mark.asyncio
    async def test_send_negative_review(self):
        bot = TelegramBot(token="test-token")
        bot.send_message = AsyncMock(return_value=True)

        result = await bot.send_negative_review(
            chat_id=-100123,
            branch_name="8 марта",
            barber_name="Павел",
            client_name="Иван",
            rating=2,
            comment="Плохо",
            created_at="2026-02-22 15:30",
            review_id=REVIEW_ID,
        )

        assert result is True
        args = bot.send_message.call_args.args
        assert "\u041d\u0435\u0433\u0430\u0442\u0438\u0432\u043d\u044b\u0439" in args[1]
        assert args[2] is not None  # reply_markup

    @pytest.mark.asyncio
    async def test_send_revenue_report(self):
        bot = TelegramBot(token="test-token")
        bot.send_message = AsyncMock(return_value=True)

        data = _revenue_data()
        result = await bot.send_revenue_report(chat_id=-100123, report_data=data)

        assert result is True
        args = bot.send_message.call_args.args
        assert "\u0412\u044b\u0440\u0443\u0447\u043a\u0430" in args[1]

    @pytest.mark.asyncio
    async def test_send_day_to_day(self):
        bot = TelegramBot(token="test-token")
        bot.send_message = AsyncMock(return_value=True)

        data = _day_to_day_data()
        result = await bot.send_day_to_day(chat_id=-100123, report_data=data)

        assert result is True
        args = bot.send_message.call_args.args
        assert "Day\\-to\\-Day" in args[1]

    @pytest.mark.asyncio
    async def test_send_kombat_monthly(self):
        bot = TelegramBot(token="test-token")
        bot.send_message = AsyncMock(return_value=True)

        data = _kombat_monthly_data()
        branch = data["branches"][0]
        result = await bot.send_kombat_monthly(
            chat_id=-100123,
            report_data=data,
            branch_data=branch,
            branch_id=BRANCH_ID,
        )

        assert result is True
        args = bot.send_message.call_args.args
        assert "\u0427\u0435\u043c\u043f\u0438\u043e\u043d" in args[1]
