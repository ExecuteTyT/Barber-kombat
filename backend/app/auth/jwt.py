import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings


class TokenPayload:
    """Decoded JWT token payload."""

    def __init__(self, user_id: uuid.UUID, organization_id: uuid.UUID, role: str):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role


def create_access_token(
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: str,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(UTC)
    expire = now + timedelta(hours=settings.jwt_expiration_hours)

    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token.

    Raises jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    return TokenPayload(
        user_id=uuid.UUID(payload["sub"]),
        organization_id=uuid.UUID(payload["org"]),
        role=payload["role"],
    )
