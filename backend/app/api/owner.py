"""Owner API — people / access management."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.people import AssignRequest, DeactivateRequest, PeopleResponse
from app.services.people import PeopleService

router = APIRouter(prefix="/owner", tags=["owner"])


@router.get("/people", response_model=PeopleResponse)
async def get_people(
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Managers, YClients staff, and pending Telegram registrations."""
    service = PeopleService(db=db)
    return await service.list_people(current_user.organization_id)


@router.post("/people/assign")
async def assign_person(
    body: AssignRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Link a Telegram id to an employee, or create a manager (admin/owner)."""
    service = PeopleService(db=db)
    return await service.assign(
        organization_id=current_user.organization_id,
        telegram_id=body.telegram_id,
        role=body.role,
        user_id=body.user_id,
        branch_id=body.branch_id,
        name=body.name,
    )


@router.post("/people/deactivate")
async def deactivate_person(
    body: DeactivateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Deactivate a user (revoke their access)."""
    service = PeopleService(db=db)
    return await service.deactivate(current_user.organization_id, body.user_id)
