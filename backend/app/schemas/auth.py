import uuid

from pydantic import BaseModel

from app.models.user import UserRole


class TelegramAuthRequest(BaseModel):
    init_data: str


class AuthUserResponse(BaseModel):
    id: uuid.UUID
    name: str
    role: UserRole
    branch_id: uuid.UUID | None = None
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserResponse


class MeResponse(BaseModel):
    id: uuid.UUID
    telegram_id: int
    name: str
    role: UserRole
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    organization_id: uuid.UUID
    grade: str | None = None
    haircut_price: int | None = None

    model_config = {"from_attributes": True}
