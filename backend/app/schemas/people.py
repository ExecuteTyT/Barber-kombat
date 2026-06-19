"""Schemas for owner-facing people / access management."""

from pydantic import BaseModel


class PersonItem(BaseModel):
    user_id: str
    name: str
    role: str
    branch_id: str | None = None
    branch_name: str | None = None
    telegram_id: int | None = None
    yclients_staff_id: int | None = None
    linked: bool


class PendingItem(BaseModel):
    telegram_id: int
    username: str | None = None
    name: str | None = None


class BranchItem(BaseModel):
    id: str
    name: str


class PeopleResponse(BaseModel):
    managers: list[PersonItem]  # owner / admin
    staff: list[PersonItem]  # barbers synced from YClients
    pending: list[PendingItem]  # opened the bot, not linked yet
    branches: list[BranchItem]


class AssignRequest(BaseModel):
    telegram_id: int
    role: str  # owner | admin | barber
    user_id: str | None = None  # link to an existing user (e.g. a YClients barber)
    branch_id: str | None = None
    name: str | None = None  # required when creating a new manager (no user_id)


class SetRoleRequest(BaseModel):
    user_id: str
    role: str  # owner | admin | barber
    branch_id: str | None = None


class DeactivateRequest(BaseModel):
    user_id: str
