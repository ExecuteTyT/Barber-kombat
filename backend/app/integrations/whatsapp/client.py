"""WhatsApp client via GreenAPI for sending review request messages."""

import httpx
import structlog

from app.config import settings

logger = structlog.stdlib.get_logger()


class WhatsAppClient:
    """Send WhatsApp messages via GreenAPI."""

    def __init__(self) -> None:
        self.api_url = settings.whatsapp_api_url.rstrip("/")
        self.token = settings.whatsapp_api_token
        self.instance_id = settings.whatsapp_instance_id
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if WhatsApp credentials are set."""
        return bool(self.api_url and self.token and self.instance_id)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to international format for GreenAPI.

        GreenAPI expects: 79001234567 (no +, no spaces, no dashes).
        Input may be: +7 (900) 123-45-67, 89001234567, 79001234567, etc.
        """
        digits = "".join(c for c in phone if c.isdigit())
        # Russian numbers starting with 8 → replace with 7
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        # If 10 digits, prepend 7 (Russian default)
        if len(digits) == 10:
            digits = "7" + digits
        return digits

    async def send_message(self, phone: str, text: str) -> bool:
        """Send a text message via GreenAPI.

        Returns True if sent successfully, False otherwise.
        """
        if not self.is_configured:
            await logger.awarning("WhatsApp not configured, skipping message", phone=phone)
            return False

        chat_id = self._normalize_phone(phone) + "@c.us"
        url = f"{self.api_url}/waInstance{self.instance_id}/sendMessage/{self.token}"

        try:
            response = await self.client.post(url, json={"chatId": chat_id, "message": text})
            response.raise_for_status()
            await logger.ainfo("WhatsApp message sent", phone=phone, chat_id=chat_id)
            return True
        except Exception:
            await logger.aexception("Failed to send WhatsApp message", phone=phone)
            return False
