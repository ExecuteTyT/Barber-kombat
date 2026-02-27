import hashlib
import hmac
import json
from urllib.parse import parse_qs, unquote


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """Validate Telegram Web App initData and return parsed user data.

    Follows the Telegram verification algorithm:
    1. Parse init_data as query string
    2. Extract hash value
    3. Build data-check-string (sorted key=value pairs, excluding hash)
    4. Compute HMAC-SHA256 using secret_key derived from bot token
    5. Compare computed hash with the provided hash

    Returns dict with parsed user info on success.
    Raises ValueError on validation failure.
    """
    parsed = parse_qs(init_data, keep_blank_values=True)

    # Extract hash
    hash_value = parsed.pop("hash", [None])[0]
    if not hash_value:
        raise ValueError("Missing hash in init_data")

    # Build data-check-string: sorted key=value pairs joined by \n
    # Each value from parse_qs is a list; take first element
    data_pairs = []
    for key in sorted(parsed.keys()):
        value = parsed[key][0]
        data_pairs.append(f"{key}={value}")
    data_check_string = "\n".join(data_pairs)

    # Compute secret key: HMAC-SHA256 of bot_token with "WebAppData" as key
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

    # Compute hash
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, hash_value):
        raise ValueError("Invalid init_data signature")

    # Parse user JSON
    user_raw = parsed.get("user", [None])[0]
    if not user_raw:
        raise ValueError("Missing user in init_data")

    user_data = json.loads(unquote(user_raw))

    return {
        "telegram_id": user_data["id"],
        "first_name": user_data.get("first_name", ""),
        "last_name": user_data.get("last_name", ""),
        "username": user_data.get("username", ""),
        "auth_date": parsed.get("auth_date", [None])[0],
        "query_id": parsed.get("query_id", [None])[0],
    }
