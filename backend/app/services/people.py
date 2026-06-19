"""People / access management for the owner.

Lets the owner see who opened the bot ("pending"), the YClients staff, and the
current managers, and link a Telegram account to an employee or create a
manager (admin/owner). Linking just sets ``users.telegram_id`` + role so the
person can authenticate via Telegram.
"""

import uuid

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.telegram_registration import TelegramRegistration
from app.models.user import User, UserRole

logger = structlog.stdlib.get_logger()

# Roles the owner is allowed to assign (chef/manager are deprecated).
ASSIGNABLE_ROLES = {UserRole.OWNER, UserRole.ADMIN, UserRole.BARBER}


class PeopleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_people(self, organization_id: uuid.UUID) -> dict:
        branches = list(
            (
                await self.db.execute(
                    select(Branch)
                    .where(
                        Branch.organization_id == organization_id,
                        Branch.is_active.is_(True),
                    )
                    .order_by(Branch.name)
                )
            ).scalars().all()
        )
        branch_name = {b.id: b.name for b in branches}

        users = list(
            (
                await self.db.execute(
                    select(User).where(
                        User.organization_id == organization_id,
                        User.is_active.is_(True),
                    )
                )
            ).scalars().all()
        )

        managers, staff = [], []
        used_tg: set[int] = set()
        for u in users:
            if u.telegram_id:
                used_tg.add(u.telegram_id)
            item = {
                "user_id": str(u.id),
                "name": u.name,
                "role": str(u.role),
                "branch_id": str(u.branch_id) if u.branch_id else None,
                "branch_name": branch_name.get(u.branch_id),
                "telegram_id": u.telegram_id,
                "yclients_staff_id": u.yclients_staff_id,
                "linked": u.telegram_id is not None,
            }
            if u.role in (UserRole.OWNER, UserRole.ADMIN):
                managers.append(item)
            elif u.role == UserRole.BARBER:
                staff.append(item)

        managers.sort(key=lambda x: (x["role"], x["name"]))
        staff.sort(key=lambda x: x["name"])

        regs = list(
            (
                await self.db.execute(
                    select(TelegramRegistration).where(
                        TelegramRegistration.organization_id == organization_id,
                        TelegramRegistration.status == "pending",
                    )
                )
            ).scalars().all()
        )
        pending = [
            {
                "telegram_id": r.telegram_id,
                "username": r.username,
                "name": " ".join(p for p in (r.first_name, r.last_name) if p) or None,
            }
            for r in regs
            if r.telegram_id not in used_tg
        ]

        return {
            "managers": managers,
            "staff": staff,
            "pending": pending,
            "branches": [{"id": str(b.id), "name": b.name} for b in branches],
        }

    async def assign(
        self,
        organization_id: uuid.UUID,
        telegram_id: int,
        role: str,
        user_id: str | None = None,
        branch_id: str | None = None,
        name: str | None = None,
    ) -> dict:
        """Link a Telegram id to an existing user, or create a new manager."""
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            return {"ok": False, "error": "bad_role"}
        if role_enum not in ASSIGNABLE_ROLES:
            return {"ok": False, "error": "bad_role"}

        # The telegram_id must be free (unique index spans active+inactive users).
        clash = (
            await self.db.execute(
                select(User).where(
                    User.organization_id == organization_id,
                    User.telegram_id == telegram_id,
                )
            )
        ).scalar_one_or_none()
        if clash is not None and (user_id is None or str(clash.id) != user_id):
            return {"ok": False, "error": "telegram_in_use"}

        bid = uuid.UUID(branch_id) if branch_id else None

        if user_id:
            user = (
                await self.db.execute(
                    select(User).where(
                        User.id == uuid.UUID(user_id),
                        User.organization_id == organization_id,
                    )
                )
            ).scalar_one_or_none()
            if user is None:
                return {"ok": False, "error": "user_not_found"}
            user.telegram_id = telegram_id
            user.role = role_enum
            if bid is not None:
                user.branch_id = bid
            user.is_active = True
        else:
            if not name:
                return {"ok": False, "error": "name_required"}
            user = User(
                id=uuid.uuid4(),
                organization_id=organization_id,
                role=role_enum,
                name=name,
                telegram_id=telegram_id,
                branch_id=bid,
                is_active=True,
            )
            self.db.add(user)

        await self.db.execute(
            update(TelegramRegistration)
            .where(
                TelegramRegistration.organization_id == organization_id,
                TelegramRegistration.telegram_id == telegram_id,
            )
            .values(status="linked")
        )
        await self.db.commit()
        await logger.ainfo(
            "Person assigned",
            telegram_id=telegram_id,
            role=str(role_enum),
            user_id=str(user.id),
        )
        return {"ok": True, "user_id": str(user.id)}

    async def set_role(
        self,
        organization_id: uuid.UUID,
        user_id: str,
        role: str,
        branch_id: str | None = None,
    ) -> dict:
        """Change an existing user's role (and optionally branch) without Telegram.

        Used to reclassify YClients-synced staff who are actually admins (no
        visit records), or to fix branch assignment. Role is NOT touched by the
        YClients sync, so this change is durable.
        """
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            return {"ok": False, "error": "bad_role"}
        if role_enum not in ASSIGNABLE_ROLES:
            return {"ok": False, "error": "bad_role"}

        user = (
            await self.db.execute(
                select(User).where(
                    User.id == uuid.UUID(user_id),
                    User.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if user is None:
            return {"ok": False, "error": "user_not_found"}

        user.role = role_enum
        if branch_id:
            user.branch_id = uuid.UUID(branch_id)
        await self.db.commit()
        await logger.ainfo(
            "Person role changed",
            user_id=str(user.id),
            role=str(role_enum),
        )
        return {"ok": True, "user_id": str(user.id)}

    async def deactivate(self, organization_id: uuid.UUID, user_id: str) -> dict:
        user = (
            await self.db.execute(
                select(User).where(
                    User.id == uuid.UUID(user_id),
                    User.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if user is None:
            return {"ok": False, "error": "user_not_found"}
        user.is_active = False
        await self.db.commit()
        return {"ok": True}
