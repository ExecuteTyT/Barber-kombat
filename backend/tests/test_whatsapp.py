"""Tests for WhatsApp client and review request flow (no real sending)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.telegram.bot import format_review_request


# ------------------------------------------------------------------
# Phone normalization
# ------------------------------------------------------------------

class TestPhoneNormalization:
    def setup_method(self):
        self.client = WhatsAppClient()

    def test_already_international(self):
        assert self.client._normalize_phone("79001234567") == "79001234567"

    def test_plus_prefix(self):
        assert self.client._normalize_phone("+79001234567") == "79001234567"

    def test_eight_prefix(self):
        assert self.client._normalize_phone("89001234567") == "79001234567"

    def test_formatted_russian(self):
        assert self.client._normalize_phone("+7 (900) 123-45-67") == "79001234567"

    def test_ten_digits(self):
        assert self.client._normalize_phone("9001234567") == "79001234567"

    def test_spaces_and_dashes(self):
        assert self.client._normalize_phone("8-900-123-45-67") == "79001234567"


# ------------------------------------------------------------------
# WhatsAppClient.send_message
# ------------------------------------------------------------------

class TestWhatsAppSendMessage:
    @pytest.mark.asyncio
    async def test_not_configured_returns_false(self):
        """If WhatsApp creds are empty, send_message returns False without HTTP call."""
        with patch("app.integrations.whatsapp.client.settings") as mock_settings:
            mock_settings.whatsapp_api_url = ""
            mock_settings.whatsapp_api_token = ""
            mock_settings.whatsapp_instance_id = ""

            client = WhatsAppClient()
            result = await client.send_message("+79001234567", "test message")
            assert result is False

    @pytest.mark.asyncio
    async def test_successful_send(self):
        """Mock HTTP POST and verify correct URL and payload."""
        with patch("app.integrations.whatsapp.client.settings") as mock_settings:
            mock_settings.whatsapp_api_url = "https://api.green-api.com"
            mock_settings.whatsapp_api_token = "test-token-123"
            mock_settings.whatsapp_instance_id = "1234567890"

            client = WhatsAppClient()

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            client._client = mock_http

            result = await client.send_message("+79001234567", "Hello!")
            assert result is True

            # Verify correct GreenAPI URL format
            mock_http.post.assert_called_once()
            call_args = mock_http.post.call_args
            url = call_args[0][0]
            assert "waInstance1234567890" in url
            assert "test-token-123" in url

            # Verify payload
            payload = call_args[1]["json"]
            assert payload["chatId"] == "79001234567@c.us"
            assert payload["message"] == "Hello!"

    @pytest.mark.asyncio
    async def test_http_error_returns_false(self):
        """If HTTP call fails, send_message returns False."""
        with patch("app.integrations.whatsapp.client.settings") as mock_settings:
            mock_settings.whatsapp_api_url = "https://api.green-api.com"
            mock_settings.whatsapp_api_token = "token"
            mock_settings.whatsapp_instance_id = "123"

            client = WhatsAppClient()

            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            ))
            client._client = mock_http

            result = await client.send_message("+79001234567", "test")
            assert result is False


# ------------------------------------------------------------------
# Review request message format
# ------------------------------------------------------------------

class TestReviewRequestFormat:
    def test_message_contains_barber_name(self):
        msg = format_review_request("Алексей", "https://example.com/review?v=123")
        assert "Алексей" in msg

    def test_message_contains_url(self):
        url = "https://example.com/review?v=123"
        msg = format_review_request("Алексей", url)
        assert url in msg

    def test_message_is_plain_text(self):
        """WhatsApp message should be plain text, no MarkdownV2 escaping."""
        msg = format_review_request("Алексей", "https://example.com")
        assert "\\" not in msg  # No escape characters


# ------------------------------------------------------------------
# Review request task logic (mocked DB)
# ------------------------------------------------------------------

class TestReviewRequestTask:
    @pytest.mark.asyncio
    async def test_skip_if_visit_not_found(self):
        """Task returns skip if visit doesn't exist."""
        from app.tasks.review_tasks import _send_review_request

        fake_id = str(uuid.uuid4())

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_session_ctx = MagicMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.database.async_session", mock_session_ctx):
            result = await _send_review_request(fake_id)
            assert result["status"] == "skip"
            assert result["reason"] == "visit_not_found"

    @pytest.mark.asyncio
    async def test_skip_if_already_sent(self):
        """Task returns skip if review_request_sent is True."""
        from app.tasks.review_tasks import _send_review_request

        fake_id = str(uuid.uuid4())

        mock_visit = MagicMock()
        mock_visit.review_request_sent = True

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_visit
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_session_ctx = MagicMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.database.async_session", mock_session_ctx):
            result = await _send_review_request(fake_id)
            assert result["status"] == "skip"
            assert result["reason"] == "already_sent"
