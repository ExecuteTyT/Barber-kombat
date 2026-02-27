"""Centralized configuration service.

CRUD operations for all config types: rating weights, PVR thresholds,
branches, users, and notification configs. Handles cache invalidation
when rating config changes.
"""

import uuid
from datetime import date

import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.notification_config import NotificationConfig
from app.models.pvr_config import PVRConfig
from app.models.rating_config import RatingConfig
from app.models.user import User

logger = structlog.stdlib.get_logger()


class ConfigService:
    """CRUD operations for all configuration types with cache invalidation."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    # --- Rating Config ---

    async def get_rating_config(
        self, organization_id: uuid.UUID
    ) -> RatingConfig | None:
        """Load RatingConfig for the organization."""
        result = await self.db.execute(
            select(RatingConfig).where(
                RatingConfig.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert_rating_config(
        self,
        organization_id: uuid.UUID,
        data: dict,
    ) -> RatingConfig:
        """Create or update RatingConfig via PostgreSQL UPSERT.

        After saving, invalidates all rating caches for the org's branches.
        """
        values = {
            "id": uuid.uuid4(),
            "organization_id": organization_id,
            **data,
        }
        stmt = pg_insert(RatingConfig).values(**values)
        update_cols = {k: getattr(stmt.excluded, k) for k in data}
        stmt = stmt.on_conflict_do_update(
            index_elements=["organization_id"],
            set_=update_cols,
        )
        await self.db.execute(stmt)
        await self.db.commit()

        await self._invalidate_rating_caches(organization_id)

        await logger.ainfo(
            "Rating config updated",
            organization_id=str(organization_id),
        )

        return await self.get_rating_config(organization_id)

    async def _invalidate_rating_caches(
        self, organization_id: uuid.UUID
    ) -> None:
        """Delete all rating cache keys for branches in this organization."""
        result = await self.db.execute(
            select(Branch.id).where(
                Branch.organization_id == organization_id,
                Branch.is_active.is_(True),
            )
        )
        branch_ids = result.scalars().all()
        today = date.today()

        for branch_id in branch_ids:
            key = f"rating:{branch_id}:{today}"
            await self.redis.delete(key)

        await logger.ainfo(
            "Rating caches invalidated",
            organization_id=str(organization_id),
            branches=len(branch_ids),
        )

    # --- PVR Config ---

    async def get_pvr_config(
        self, organization_id: uuid.UUID
    ) -> PVRConfig | None:
        """Load PVRConfig for the organization."""
        result = await self.db.execute(
            select(PVRConfig).where(
                PVRConfig.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert_pvr_config(
        self,
        organization_id: uuid.UUID,
        data: dict,
    ) -> PVRConfig:
        """Create or update PVRConfig via PostgreSQL UPSERT."""
        values = {
            "id": uuid.uuid4(),
            "organization_id": organization_id,
            **data,
        }
        stmt = pg_insert(PVRConfig).values(**values)
        update_cols = {k: getattr(stmt.excluded, k) for k in data}
        stmt = stmt.on_conflict_do_update(
            index_elements=["organization_id"],
            set_=update_cols,
        )
        await self.db.execute(stmt)
        await self.db.commit()

        await logger.ainfo(
            "PVR config updated",
            organization_id=str(organization_id),
        )

        return await self.get_pvr_config(organization_id)

    # --- Branch CRUD ---

    async def list_branches(
        self, organization_id: uuid.UUID
    ) -> list[Branch]:
        """List all branches for the organization."""
        result = await self.db.execute(
            select(Branch)
            .where(Branch.organization_id == organization_id)
            .order_by(Branch.name)
        )
        return list(result.scalars().all())

    async def get_branch(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
    ) -> Branch | None:
        """Get a single branch by ID within the organization."""
        result = await self.db.execute(
            select(Branch).where(
                Branch.id == branch_id,
                Branch.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_branch(
        self,
        organization_id: uuid.UUID,
        data: dict,
    ) -> Branch:
        """Create a new branch."""
        branch = Branch(organization_id=organization_id, **data)
        self.db.add(branch)
        await self.db.commit()
        await self.db.refresh(branch)

        await logger.ainfo(
            "Branch created",
            branch_id=str(branch.id),
            organization_id=str(organization_id),
        )
        return branch

    async def update_branch(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        data: dict,
    ) -> Branch | None:
        """Update an existing branch. Returns None if not found."""
        branch = await self.get_branch(organization_id, branch_id)
        if branch is None:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(branch, key, value)

        await self.db.commit()
        await self.db.refresh(branch)
        return branch

    # --- User CRUD ---

    async def list_users(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
    ) -> list[User]:
        """List users, optionally filtered by branch."""
        stmt = select(User).where(User.organization_id == organization_id)
        if branch_id is not None:
            stmt = stmt.where(User.branch_id == branch_id)
        stmt = stmt.order_by(User.name)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> User | None:
        """Get a single user by ID within the organization."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        organization_id: uuid.UUID,
        data: dict,
    ) -> User:
        """Create a new user."""
        user = User(organization_id=organization_id, **data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        await logger.ainfo(
            "User created",
            user_id=str(user.id),
            organization_id=str(organization_id),
            role=data.get("role", "unknown"),
        )
        return user

    async def update_user(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: dict,
    ) -> User | None:
        """Update an existing user. Returns None if not found."""
        user = await self.get_user(organization_id, user_id)
        if user is None:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(user, key, value)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    # --- Notification Config CRUD ---

    async def list_notifications(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
    ) -> list[NotificationConfig]:
        """List notification configs, optionally filtered by branch."""
        stmt = select(NotificationConfig).where(
            NotificationConfig.organization_id == organization_id
        )
        if branch_id is not None:
            stmt = stmt.where(NotificationConfig.branch_id == branch_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_notification(
        self,
        organization_id: uuid.UUID,
        data: dict,
    ) -> NotificationConfig:
        """Create a notification config entry."""
        notif = NotificationConfig(organization_id=organization_id, **data)
        self.db.add(notif)
        await self.db.commit()
        await self.db.refresh(notif)

        await logger.ainfo(
            "Notification config created",
            notification_id=str(notif.id),
            organization_id=str(organization_id),
            notification_type=data.get("notification_type"),
        )
        return notif

    async def update_notification(
        self,
        organization_id: uuid.UUID,
        notification_id: uuid.UUID,
        data: dict,
    ) -> NotificationConfig | None:
        """Update a notification config. Returns None if not found."""
        result = await self.db.execute(
            select(NotificationConfig).where(
                NotificationConfig.id == notification_id,
                NotificationConfig.organization_id == organization_id,
            )
        )
        notif = result.scalar_one_or_none()
        if notif is None:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(notif, key, value)

        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    async def delete_notification(
        self,
        organization_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> bool:
        """Delete a notification config. Returns True if deleted."""
        result = await self.db.execute(
            select(NotificationConfig).where(
                NotificationConfig.id == notification_id,
                NotificationConfig.organization_id == organization_id,
            )
        )
        notif = result.scalar_one_or_none()
        if notif is None:
            return False

        await self.db.delete(notif)
        await self.db.commit()
        return True
