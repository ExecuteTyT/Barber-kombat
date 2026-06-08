import uuid
from collections.abc import Callable
from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import TokenPayload, decode_access_token
from app.database import get_db
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate JWT, return the current user."""
    try:
        payload: TokenPayload = decode_access_token(credentials.credentials)
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    result = await db.execute(select(User).where(User.id == payload.user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_role(*roles: UserRole) -> Callable:
    """Dependency factory that checks if the current user has one of the required roles."""

    async def check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return check_role


def require_branch_access(*roles: UserRole) -> Callable:
    """Dependency factory for endpoints with a ``branch_id`` path parameter.

    Checks role membership AND branch ownership: an OWNER may access any branch
    in their organization, but an ADMIN (or other branch-scoped role) may only
    access their own ``branch_id``. Use on routes shaped ``/.../{branch_id}``.
    """

    async def check_access(
        branch_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        # Owner sees any branch in the org; everyone else is pinned to their own.
        if current_user.role != UserRole.OWNER and current_user.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this branch",
            )
        return current_user

    return check_access


def get_org_id(current_user: Annotated[User, Depends(get_current_user)]) -> uuid.UUID:
    """Extract organization_id from the current user for query filtering."""
    return current_user.organization_id
