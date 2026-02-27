import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import jwt as pyjwt
import pytest

from app.auth.jwt import create_access_token, decode_access_token
from app.auth.telegram import validate_init_data
from app.config import settings

# --- Test constants ---
BOT_TOKEN = "1234567890:ABCDEFghijklMNOPqrstUVWXyz123456789"
USER_ID = uuid.uuid4()
ORG_ID = uuid.uuid4()


# --- Helpers ---


def build_init_data(
    telegram_id: int = 123456789,
    first_name: str = "Test",
    bot_token: str = BOT_TOKEN,
    extra_params: dict | None = None,
) -> str:
    """Build a valid Telegram initData string with correct HMAC signature."""
    user_data = json.dumps(
        {"id": telegram_id, "first_name": first_name, "last_name": "User", "username": "testuser"}
    )

    params = {
        "query_id": "AAH1234567890",
        "user": user_data,
        "auth_date": str(int(datetime.now(UTC).timestamp())),
    }
    if extra_params:
        params.update(extra_params)

    # Build data-check-string
    data_check_string = "\n".join(f"{k}={params[k]}" for k in sorted(params.keys()))

    # Compute hash
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    params["hash"] = hash_value
    return urlencode(params)


# --- Tests: validate_init_data ---


class TestValidateInitData:
    def test_valid_init_data(self):
        init_data = build_init_data(telegram_id=999, bot_token=BOT_TOKEN)
        result = validate_init_data(init_data, BOT_TOKEN)

        assert result["telegram_id"] == 999
        assert result["first_name"] == "Test"
        assert result["last_name"] == "User"
        assert result["username"] == "testuser"

    def test_invalid_hash(self):
        init_data = build_init_data(bot_token=BOT_TOKEN)
        # Tamper with the hash
        init_data = init_data.replace("hash=", "hash=0000")

        with pytest.raises(ValueError, match="Invalid init_data signature"):
            validate_init_data(init_data, BOT_TOKEN)

    def test_missing_hash(self):
        user_data = json.dumps({"id": 123, "first_name": "Test"})
        init_data = urlencode({"user": user_data, "auth_date": "1234567890"})

        with pytest.raises(ValueError, match="Missing hash"):
            validate_init_data(init_data, BOT_TOKEN)

    def test_missing_user(self):
        params = {"auth_date": "1234567890"}
        data_check_string = "\n".join(f"{k}={params[k]}" for k in sorted(params.keys()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        hash_value = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        params["hash"] = hash_value
        init_data = urlencode(params)

        with pytest.raises(ValueError, match="Missing user"):
            validate_init_data(init_data, BOT_TOKEN)

    def test_wrong_bot_token(self):
        init_data = build_init_data(bot_token=BOT_TOKEN)

        with pytest.raises(ValueError, match="Invalid init_data signature"):
            validate_init_data(init_data, "wrong_token")


# --- Tests: JWT ---


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(USER_ID, ORG_ID, "barber")
        payload = decode_access_token(token)

        assert payload.user_id == USER_ID
        assert payload.organization_id == ORG_ID
        assert payload.role == "barber"

    def test_expired_token(self):
        # Create a token that's already expired
        now = datetime.now(UTC)
        expired = now - timedelta(hours=25)

        payload = {
            "sub": str(USER_ID),
            "org": str(ORG_ID),
            "role": "barber",
            "iat": expired,
            "exp": expired + timedelta(hours=1),  # expired 24h ago
        }
        token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_token(self):
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token("not.a.valid.token")

    def test_wrong_secret(self):
        payload = {
            "sub": str(USER_ID),
            "org": str(ORG_ID),
            "role": "barber",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")

        with pytest.raises(pyjwt.InvalidSignatureError):
            decode_access_token(token)

    def test_all_roles(self):
        for role in ["owner", "manager", "chef", "barber", "admin"]:
            token = create_access_token(USER_ID, ORG_ID, role)
            payload = decode_access_token(token)
            assert payload.role == role

    def test_token_contains_expected_claims(self):
        token = create_access_token(USER_ID, ORG_ID, "owner")
        raw = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

        assert raw["sub"] == str(USER_ID)
        assert raw["org"] == str(ORG_ID)
        assert raw["role"] == "owner"
        assert "iat" in raw
        assert "exp" in raw
        assert raw["exp"] - raw["iat"] == settings.jwt_expiration_hours * 3600
