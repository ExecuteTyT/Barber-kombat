from typing import Annotated

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.auth.telegram import validate_init_data
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import AuthUserResponse, MeResponse, TelegramAuthRequest, TokenResponse

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])


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
        await logger.awarning("Auth failed: user not registered", telegram_id=telegram_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not registered in the system",
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
    - ``role``: login as the first user with this role (owner/chef/barber/admin)
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
        # Return list of available users for the dev login UI
        result = await db.execute(select(User).where(User.is_active.is_(True)))
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

    result = await db.execute(select(User).where(User.is_active.is_(True)))
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
