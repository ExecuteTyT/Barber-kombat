"""HMAC-SHA256 signature validation for YClients webhooks."""

import hashlib
import hmac

import structlog

logger = structlog.stdlib.get_logger()


def validate_webhook_signature(
    raw_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Validate the HMAC-SHA256 signature of a YClients webhook.

    Args:
        raw_body: The raw request body bytes.
        signature: The signature from the request header.
        secret: The webhook secret from settings.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not secret:
        logger.warning("Webhook secret not configured, skipping validation")
        return True

    if not signature:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
