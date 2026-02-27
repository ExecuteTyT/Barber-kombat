"""CLI commands for Barber Kombat.

Usage:
    python -m app.cli seed --org-name "Barbershop" --org-slug "barbershop" \
        --owner-telegram-id 123456789 --owner-name "Ivan"

    python -m app.cli seed-demo   # Populate DB with full demo data for testing

    python -m app.cli monthly-reset --month=2026-01
"""

import asyncio
import random
import uuid
from datetime import date, timedelta

import click
import structlog

logger = structlog.stdlib.get_logger()


def _run_async(coro):
    """Run an async coroutine from a sync Click command."""
    return asyncio.run(coro)


@click.group()
def cli():
    """Barber Kombat management CLI."""
    pass


@cli.command()
@click.option("--org-name", required=True, help="Organization name")
@click.option("--org-slug", required=True, help="Organization slug (unique)")
@click.option(
    "--owner-telegram-id",
    required=True,
    type=int,
    help="Owner's Telegram ID",
)
@click.option("--owner-name", required=True, help="Owner's display name")
@click.option("--branch-name", default="Main Branch", help="First branch name")
@click.option("--branch-address", default="", help="Branch address")
@click.option(
    "--yclients-company-id",
    type=int,
    default=None,
    help="YClients company ID for the branch",
)
def seed(
    org_name,
    org_slug,
    owner_telegram_id,
    owner_name,
    branch_name,
    branch_address,
    yclients_company_id,
):
    """Create initial organization, branch, owner, and default configs."""
    _run_async(
        _seed(
            org_name,
            org_slug,
            owner_telegram_id,
            owner_name,
            branch_name,
            branch_address,
            yclients_company_id,
        )
    )


async def _seed(
    org_name: str,
    org_slug: str,
    owner_telegram_id: int,
    owner_name: str,
    branch_name: str,
    branch_address: str,
    yclients_company_id: int | None,
):
    """Async implementation of the seed command."""
    from app.database import async_session
    from app.models.branch import Branch
    from app.models.organization import Organization
    from app.models.pvr_config import PVRConfig
    from app.models.rating_config import RatingConfig
    from app.models.user import User, UserRole

    async with async_session() as db:
        # 1. Organization
        org = Organization(name=org_name, slug=org_slug)
        db.add(org)
        await db.flush()

        # 2. Branch
        branch = Branch(
            organization_id=org.id,
            name=branch_name,
            address=branch_address,
            yclients_company_id=yclients_company_id,
        )
        db.add(branch)
        await db.flush()

        # 3. Owner user
        owner = User(
            organization_id=org.id,
            branch_id=None,
            telegram_id=owner_telegram_id,
            role=UserRole.OWNER,
            name=owner_name,
        )
        db.add(owner)

        # 4. Rating config with defaults
        rating_config = RatingConfig(
            organization_id=org.id,
            revenue_weight=20,
            cs_weight=20,
            products_weight=25,
            extras_weight=25,
            reviews_weight=10,
            prize_gold_pct=0.5,
            prize_silver_pct=0.3,
            prize_bronze_pct=0.1,
            extra_services=[
                "воск",
                "камуфляж головы",
                "камуфляж бороды",
                "массаж",
                "премиум помывка",
            ],
        )
        db.add(rating_config)

        # 5. PVR config with defaults
        pvr_config = PVRConfig(
            organization_id=org.id,
            thresholds=[
                {"amount": 30_000_000, "bonus": 1_000_000},
                {"amount": 35_000_000, "bonus": 1_500_000},
                {"amount": 40_000_000, "bonus": 2_000_000},
                {"amount": 50_000_000, "bonus": 3_000_000},
                {"amount": 60_000_000, "bonus": 4_000_000},
                {"amount": 80_000_000, "bonus": 5_000_000},
            ],
            count_products=False,
            count_certificates=False,
        )
        db.add(pvr_config)

        await db.commit()

        click.echo(f"Organization '{org_name}' created (id={org.id})")
        click.echo(f"Branch '{branch_name}' created (id={branch.id})")
        click.echo(f"Owner '{owner_name}' created (id={owner.id})")
        click.echo("Rating config and PVR config created with defaults.")


@cli.command("seed-demo")
def seed_demo():
    """Populate DB with full realistic demo data for local testing.

    Creates: organization, 2 branches, 8 users (barbers + chef + owner + admin),
    7 days of DailyRating & Visit records, PVR records, Plans, Reviews, Reports.
    No YClients or Telegram required.
    """
    _run_async(_seed_demo())


async def _seed_demo():
    """Async implementation of seed-demo."""
    from app.database import async_session
    from app.models.branch import Branch
    from app.models.client import Client
    from app.models.daily_rating import DailyRating
    from app.models.notification_config import NotificationConfig
    from app.models.organization import Organization
    from app.models.plan import Plan
    from app.models.pvr_config import PVRConfig
    from app.models.pvr_record import PVRRecord
    from app.models.rating_config import RatingConfig
    from app.models.report import Report
    from app.models.review import Review
    from app.models.user import User, UserRole
    from app.models.visit import Visit

    today = date.today()
    month_start = today.replace(day=1)

    async with async_session() as db:
        # ---- 1. Organization ----
        org = Organization(name="Demo Barbershop", slug="demo")
        db.add(org)
        await db.flush()
        org_id = org.id
        click.echo(f"[OK] Organization 'Demo Barbershop' created (id={org_id})")

        # ---- 2. Branches ----
        branch1 = Branch(
            organization_id=org_id,
            name="Центральный",
            address="ул. Пушкина, д. 10",
            yclients_company_id=100001,
            telegram_group_id=-100_000_001,
        )
        branch2 = Branch(
            organization_id=org_id,
            name="Южный",
            address="пр. Ленина, д. 42",
            yclients_company_id=100002,
            telegram_group_id=-100_000_002,
        )
        db.add_all([branch1, branch2])
        await db.flush()
        click.echo(
            f"[OK] Branches: '{branch1.name}' (id={branch1.id}), '{branch2.name}' (id={branch2.id})"
        )

        # ---- 3. Users ----
        # Barbers for branch 1
        barbers_b1_data = [
            ("Алексей Волков", "top", 250000, 1001),
            ("Дмитрий Орлов", "senior", 200000, 1002),
            ("Михаил Козлов", "middle", 180000, 1003),
        ]
        # Barbers for branch 2
        barbers_b2_data = [
            ("Иван Петров", "top", 250000, 2001),
            ("Сергей Новиков", "senior", 200000, 2002),
        ]

        barbers_b1 = []
        barbers_b2 = []
        tg_id = 900_000_001

        for name, grade, price, staff_id in barbers_b1_data:
            u = User(
                organization_id=org_id,
                branch_id=branch1.id,
                telegram_id=tg_id,
                role=UserRole.BARBER,
                name=name,
                grade=grade,
                haircut_price=price,
                yclients_staff_id=staff_id,
            )
            barbers_b1.append(u)
            tg_id += 1

        for name, grade, price, staff_id in barbers_b2_data:
            u = User(
                organization_id=org_id,
                branch_id=branch2.id,
                telegram_id=tg_id,
                role=UserRole.BARBER,
                name=name,
                grade=grade,
                haircut_price=price,
                yclients_staff_id=staff_id,
            )
            barbers_b2.append(u)
            tg_id += 1

        # Chef (manages branch 1)
        chef = User(
            organization_id=org_id,
            branch_id=branch1.id,
            telegram_id=tg_id,
            role=UserRole.CHEF,
            name="Анна Смирнова",
        )
        tg_id += 1

        # Owner
        owner = User(
            organization_id=org_id,
            branch_id=None,
            telegram_id=tg_id,
            role=UserRole.OWNER,
            name="Павел Демо",
        )
        tg_id += 1

        # Admin
        admin = User(
            organization_id=org_id,
            branch_id=branch1.id,
            telegram_id=tg_id,
            role=UserRole.ADMIN,
            name="Елена Админ",
        )
        tg_id += 1

        all_users = barbers_b1 + barbers_b2 + [chef, owner, admin]
        db.add_all(all_users)
        await db.flush()
        all_barbers = barbers_b1 + barbers_b2
        click.echo(f"[OK] Created {len(all_users)} users ({len(all_barbers)} barbers)")

        # ---- 4. Rating Config ----
        rating_config = RatingConfig(
            organization_id=org_id,
            revenue_weight=20,
            cs_weight=20,
            products_weight=25,
            extras_weight=25,
            reviews_weight=10,
            prize_gold_pct=0.5,
            prize_silver_pct=0.3,
            prize_bronze_pct=0.1,
            extra_services=[
                "воск",
                "камуфляж головы",
                "камуфляж бороды",
                "массаж",
                "премиум помывка",
            ],
        )
        db.add(rating_config)

        # ---- 5. PVR Config ----
        pvr_config = PVRConfig(
            organization_id=org_id,
            thresholds=[
                {"amount": 30_000_000, "bonus": 1_000_000},
                {"amount": 35_000_000, "bonus": 1_500_000},
                {"amount": 40_000_000, "bonus": 2_000_000},
                {"amount": 50_000_000, "bonus": 3_000_000},
                {"amount": 60_000_000, "bonus": 4_000_000},
                {"amount": 80_000_000, "bonus": 5_000_000},
            ],
            count_products=False,
            count_certificates=False,
        )
        db.add(pvr_config)

        # ---- 6. Plans (current month) ----
        plan1 = Plan(
            organization_id=org_id,
            branch_id=branch1.id,
            month=month_start,
            target_amount=300_000_00,  # 300,000 rub in kopecks
            current_amount=0,
            percentage=0.0,
        )
        plan2 = Plan(
            organization_id=org_id,
            branch_id=branch2.id,
            month=month_start,
            target_amount=200_000_00,  # 200,000 rub
            current_amount=0,
            percentage=0.0,
        )
        db.add_all([plan1, plan2])
        await db.flush()

        # ---- 7. Demo Clients ----
        client_names = [
            "Андрей К.",
            "Борис М.",
            "Виктор Н.",
            "Григорий П.",
            "Денис С.",
            "Евгений Т.",
            "Жора У.",
            "Захар Ф.",
            "Игорь Х.",
            "Константин Ц.",
        ]
        clients = []
        for i, cn in enumerate(client_names):
            c = Client(
                organization_id=org_id,
                yclients_client_id=50_000 + i,
                phone=f"+7900{3000000 + i}",
                name=cn,
                total_visits=random.randint(1, 20),
            )
            clients.append(c)
        db.add_all(clients)
        await db.flush()

        # ---- 8. Daily Ratings + Visits (last 7 days) ----
        yclients_record_seq = 800_000
        plan1_revenue_total = 0
        plan2_revenue_total = 0

        for day_offset in range(7, 0, -1):
            d = today - timedelta(days=day_offset)

            for branch, barbers, plan_acc in [
                (branch1, barbers_b1, "b1"),
                (branch2, barbers_b2, "b2"),
            ]:
                scores = []
                for barber in barbers:
                    # Generate realistic raw values
                    revenue = random.randint(800000, 2500000)  # 8k-25k rub in kopecks
                    cs_value = round(random.uniform(1.5, 3.5), 2)
                    products_count = random.randint(0, 5)
                    extras_count = random.randint(0, 4)
                    reviews_avg = (
                        round(random.uniform(3.5, 5.0), 1) if random.random() > 0.3 else None
                    )

                    # Compute rough normalized scores
                    rev_score = min(100.0, (revenue / 2_500_000) * 100)
                    cs_score = min(100.0, (cs_value / 3.5) * 100)
                    prod_score = min(100.0, (products_count / 5) * 100)
                    ext_score = min(100.0, (extras_count / 4) * 100)
                    rev_review_score = ((reviews_avg / 5.0) * 100) if reviews_avg else 0.0

                    total = round(
                        rev_score * 0.20
                        + cs_score * 0.20
                        + prod_score * 0.25
                        + ext_score * 0.25
                        + rev_review_score * 0.10,
                        2,
                    )
                    scores.append(
                        (
                            barber,
                            total,
                            revenue,
                            cs_value,
                            products_count,
                            extras_count,
                            reviews_avg,
                            rev_score,
                            cs_score,
                            prod_score,
                            ext_score,
                            rev_review_score,
                        )
                    )

                    # Accumulate plan revenue
                    if plan_acc == "b1":
                        plan1_revenue_total += revenue
                    else:
                        plan2_revenue_total += revenue

                # Sort by total desc for ranking
                scores.sort(key=lambda x: x[1], reverse=True)

                for rank, (
                    barber,
                    total,
                    revenue,
                    cs_value,
                    products_count,
                    extras_count,
                    reviews_avg,
                    rev_score,
                    cs_score,
                    prod_score,
                    ext_score,
                    rev_review_score,
                ) in enumerate(scores, 1):
                    dr = DailyRating(
                        organization_id=org_id,
                        branch_id=branch.id,
                        barber_id=barber.id,
                        date=d,
                        revenue=revenue,
                        cs_value=cs_value,
                        products_count=products_count,
                        extras_count=extras_count,
                        reviews_avg=reviews_avg,
                        revenue_score=round(rev_score, 2),
                        cs_score=round(cs_score, 2),
                        products_score=round(prod_score, 2),
                        extras_score=round(ext_score, 2),
                        reviews_score=round(rev_review_score, 2),
                        total_score=total,
                        rank=rank,
                    )
                    db.add(dr)

                    # Create 2-4 visits per barber per day
                    num_visits = random.randint(2, 4)
                    visit_revenue_each = revenue // num_visits
                    for _v_idx in range(num_visits):
                        client = random.choice(clients)
                        v = Visit(
                            organization_id=org_id,
                            branch_id=branch.id,
                            barber_id=barber.id,
                            client_id=client.id,
                            yclients_record_id=yclients_record_seq,
                            date=d,
                            revenue=visit_revenue_each,
                            services_revenue=int(visit_revenue_each * 0.85),
                            products_revenue=int(visit_revenue_each * 0.15),
                            extras_count=random.randint(0, 2),
                            products_count=random.randint(0, 1),
                            payment_type=random.choice(["card", "cash", "card"]),
                            status="completed",
                        )
                        db.add(v)
                        yclients_record_seq += 1

        click.echo("[OK] Created 7 days of daily ratings and visits")

        # Update plan current amounts
        plan1.current_amount = plan1_revenue_total
        plan1.percentage = (
            round((plan1_revenue_total / plan1.target_amount) * 100, 1)
            if plan1.target_amount
            else 0
        )
        plan2.current_amount = plan2_revenue_total
        plan2.percentage = (
            round((plan2_revenue_total / plan2.target_amount) * 100, 1)
            if plan2.target_amount
            else 0
        )

        # ---- 9. PVR Records (current month) ----
        for barber in all_barbers:
            cum_revenue = random.randint(15_000_000, 45_000_000)
            # Determine threshold reached
            thresholds_reached = []
            bonus = 0
            current_threshold = None
            for t in pvr_config.thresholds:
                if cum_revenue >= t["amount"]:
                    thresholds_reached.append(
                        {
                            "amount": t["amount"],
                            "reached_at": str(today - timedelta(days=random.randint(1, 7))),
                        }
                    )
                    bonus = t["bonus"]
                    current_threshold = t["amount"]
                else:
                    break

            pvr = PVRRecord(
                organization_id=org_id,
                barber_id=barber.id,
                month=month_start,
                cumulative_revenue=cum_revenue,
                current_threshold=current_threshold,
                bonus_amount=bonus,
                thresholds_reached=thresholds_reached if thresholds_reached else None,
            )
            db.add(pvr)
        click.echo(f"[OK] Created PVR records for {len(all_barbers)} barbers")

        # ---- 10. Reviews ----
        review_comments = [
            "Отличная стрижка, буду приходить ещё!",
            "Хороший сервис, но пришлось ждать",
            "Супер! Рекомендую всем",
            None,
            "Нормально",
            "Борода огонь!",
        ]
        for _ in range(8):
            barber = random.choice(all_barbers)
            r = Review(
                organization_id=org_id,
                branch_id=barber.branch_id,
                barber_id=barber.id,
                client_id=random.choice(clients).id,
                rating=random.randint(3, 5),
                comment=random.choice(review_comments),
                source=random.choice(["yclients", "google", "internal"]),
                status="new",
            )
            db.add(r)
        click.echo("[OK] Created 8 demo reviews")

        # ---- 11. Reports ----
        yesterday = today - timedelta(days=1)
        report_daily = Report(
            organization_id=org_id,
            branch_id=None,
            type="daily_revenue",
            date=yesterday,
            data={
                "branches": [
                    {
                        "branch_id": str(branch1.id),
                        "name": branch1.name,
                        "revenue_today": 4_500_000,
                        "revenue_mtd": plan1_revenue_total,
                        "plan_target": plan1.target_amount,
                        "plan_percentage": plan1.percentage,
                        "barbers_in_shift": len(barbers_b1),
                        "barbers_total": len(barbers_b1),
                    },
                    {
                        "branch_id": str(branch2.id),
                        "name": branch2.name,
                        "revenue_today": 3_200_000,
                        "revenue_mtd": plan2_revenue_total,
                        "plan_target": plan2.target_amount,
                        "plan_percentage": plan2.percentage,
                        "barbers_in_shift": len(barbers_b2),
                        "barbers_total": len(barbers_b2),
                    },
                ],
                "network_total_today": 7_700_000,
                "network_total_mtd": plan1_revenue_total + plan2_revenue_total,
            },
            delivered_telegram=True,
        )
        db.add(report_daily)

        # Notification configs
        for branch, chat_id in [(branch1, -100_000_001), (branch2, -100_000_002)]:
            nc = NotificationConfig(
                organization_id=org_id,
                branch_id=branch.id,
                notification_type="daily_report",
                telegram_chat_id=chat_id,
                is_enabled=True,
            )
            db.add(nc)
        click.echo("[OK] Created reports and notification configs")

        await db.commit()

        # ---- Print summary ----
        click.echo("")
        click.echo("=" * 60)
        click.echo("  DEMO DATA CREATED SUCCESSFULLY")
        click.echo("=" * 60)
        click.echo("")
        click.echo("  Demo users (telegram_id → role → name):")
        for u in all_users:
            branch_name = ""
            if u.branch_id == branch1.id:
                branch_name = f" [{branch1.name}]"
            elif u.branch_id == branch2.id:
                branch_name = f" [{branch2.name}]"
            click.echo(f"    {u.telegram_id} → {u.role.value:>7} → {u.name}{branch_name}")
        click.echo("")
        click.echo("  To login via dev endpoint:")
        click.echo("    POST /api/v1/auth/dev-login")
        click.echo('    Body: {"telegram_id": 900000001}')
        click.echo("")
        click.echo("  Or use the dev login selector in the browser at http://localhost:3000")
        click.echo("=" * 60)


@cli.command("sync-initial")
@click.option("--org-id", required=True, type=str, help="Organization UUID")
def sync_initial(org_id: str):
    """Run initial YClients synchronization for an organization."""
    _run_async(_sync_initial(uuid.UUID(org_id)))


async def _sync_initial(org_id: uuid.UUID):
    """Async implementation of sync-initial."""
    from app.database import async_session
    from app.redis import redis_client
    from app.services.sync import SyncService

    async with async_session() as db:
        sync_service = SyncService(db=db, redis=redis_client)
        await sync_service.initial_sync(org_id)
        click.echo(f"Initial sync completed for org {org_id}")


@cli.command("monthly-reset")
@click.option(
    "--month",
    required=True,
    type=str,
    help="Month to finalize in YYYY-MM format (e.g. 2026-01)",
)
@click.option(
    "--org-id",
    default=None,
    type=str,
    help="Optional: only reset a single organization (UUID)",
)
def monthly_reset(month: str, org_id: str | None):
    """Finalize a month: determine champions, freeze prizes, reset PVR, copy plans."""
    try:
        parts = month.split("-")
        target_month = date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        click.echo(f"Invalid month format: {month}. Use YYYY-MM (e.g. 2026-01).")
        raise SystemExit(1) from None

    click.echo(f"Running monthly reset for {target_month.strftime('%B %Y')}...")

    if org_id:
        result = _run_async(_monthly_reset_single(uuid.UUID(org_id), target_month))
    else:
        result = _run_async(_monthly_reset_all(target_month))

    click.echo(f"Monthly reset completed: {result}")


async def _monthly_reset_all(target_month: date) -> dict:
    """Run monthly reset for all organizations."""
    from app.database import async_session
    from app.services.monthly_reset import MonthlyResetService

    async with async_session() as db:
        service = MonthlyResetService(db=db)
        return await service.reset_all_organizations(target_month)


async def _monthly_reset_single(org_id: uuid.UUID, target_month: date) -> dict:
    """Run monthly reset for a single organization."""
    from app.database import async_session
    from app.services.monthly_reset import MonthlyResetService

    async with async_session() as db:
        service = MonthlyResetService(db=db)
        return await service.reset_organization(org_id, target_month)


if __name__ == "__main__":
    cli()
