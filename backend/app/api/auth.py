import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.auth.telegram import validate_init_data
from app.config import settings
from app.database import get_db
from app.models.organization import Organization
from app.models.telegram_registration import TelegramRegistration
from app.models.user import User
from app.schemas.auth import AuthUserResponse, MeResponse, TelegramAuthRequest, TokenResponse

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])


async def _record_pending_registration(db: AsyncSession, tg_data: dict) -> None:
    """Upsert a pending Telegram registration so the owner can link it later.

    Best-effort: needs an organization to attach to (single-tenant deployment).
    On conflict, refresh the profile fields but keep the existing status (so an
    owner-set "ignored"/"linked" isn't reset).
    """
    org_id = (
        await db.execute(
            select(Organization.id).where(Organization.is_active.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if org_id is None:
        return

    stmt = pg_insert(TelegramRegistration).values(
        id=uuid.uuid4(),
        organization_id=org_id,
        telegram_id=tg_data["telegram_id"],
        username=tg_data.get("username") or None,
        first_name=tg_data.get("first_name") or None,
        last_name=tg_data.get("last_name") or None,
        status="pending",
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_tg_reg_org_tgid",
        set_={
            "username": stmt.excluded.username,
            "first_name": stmt.excluded.first_name,
            "last_name": stmt.excluded.last_name,
        },
    )
    await db.execute(stmt)
    await db.commit()


@router.post("/telegram", response_model=TokenResponse)
async def auth_telegram(
    body: TelegramAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate via Telegram Web App initData."""
    # Validate Telegram signature
    try:
        tg_data = validate_init_data(body.init_data, settings.telegram_bot_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from None

    telegram_id = tg_data["telegram_id"]

    # Find user by telegram_id
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        # Not linked yet — record the Telegram user as "pending" so the owner can
        # map them to an employee/manager, then tell the client to wait.
        await _record_pending_registration(db, tg_data)
        await logger.awarning("Auth: pending registration", telegram_id=telegram_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "pending_registration",
                "telegram_id": telegram_id,
                "username": tg_data.get("username") or None,
                "name": (
                    f"{tg_data.get('first_name', '')} {tg_data.get('last_name', '')}".strip()
                    or None
                ),
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Create JWT
    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )

    await logger.ainfo("User authenticated", user_id=str(user.id), role=user.role)

    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expiration_hours * 3600,
        user=AuthUserResponse(
            id=user.id,
            name=user.name,
            role=user.role,
            branch_id=user.branch_id,
            organization_id=user.organization_id,
        ),
    )


@router.post("/dev-login")
async def dev_login(
    db: Annotated[AsyncSession, Depends(get_db)],
    telegram_id: Annotated[int | None, Body(embed=True)] = None,
    role: Annotated[str | None, Body(embed=True)] = None,
):
    """Development-only login endpoint. Bypasses Telegram auth.

    Use one of:
    - ``telegram_id``: login as specific user by their telegram_id
    - ``role``: login as the first user with this role (owner/barber/admin)
    - neither: returns list of available demo users
    """
    if not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    if telegram_id:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
    elif role:
        result = await db.execute(
            select(User).where(User.role == role, User.is_active.is_(True)).limit(1)
        )
        user = result.scalar_one_or_none()
    else:
        # Return list of available users for the dev login UI (only users with telegram_id)
        result = await db.execute(
            select(User).where(User.is_active.is_(True), User.telegram_id.isnot(None))
        )
        users = result.scalars().all()
        return {
            "users": [
                {
                    "telegram_id": u.telegram_id,
                    "name": u.name,
                    "role": u.role,
                    "branch_id": str(u.branch_id) if u.branch_id else None,
                }
                for u in users
            ],
        }

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )

    await logger.ainfo("Dev login", user_id=str(user.id), role=user.role)

    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expiration_hours * 3600,
        user=AuthUserResponse(
            id=user.id,
            name=user.name,
            role=user.role,
            branch_id=user.branch_id,
            organization_id=user.organization_id,
        ),
    )


@router.get("/dev-users")
async def dev_users(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Development-only: list available demo users for the login selector."""
    if not settings.is_development:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    result = await db.execute(
        select(User).where(User.is_active.is_(True), User.telegram_id.isnot(None))
    )
    users = result.scalars().all()
    return {
        "users": [
            {
                "telegram_id": u.telegram_id,
                "name": u.name,
                "role": u.role,
                "branch_id": str(u.branch_id) if u.branch_id else None,
            }
            for u in users
        ],
    }


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get current authenticated user info."""
    # Reload with branch relationship for branch_name
    result = await db.execute(
        select(User).options(selectinload(User.branch)).where(User.id == current_user.id)
    )
    user = result.scalar_one()

    return MeResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        name=user.name,
        role=user.role,
        branch_id=user.branch_id,
        branch_name=user.branch.name if user.branch else None,
        organization_id=user.organization_id,
        grade=user.grade,
        haircut_price=user.haircut_price,
    )
