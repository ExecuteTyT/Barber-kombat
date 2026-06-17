"""Tests for SyncService mapping helpers and logic."""

import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.yclients.schemas import (
    YClientComment,
    YClientGoodsTransaction,
    YClientRecord,
    YClientRecordClient,
    YClientService,
)
from app.models.review import ReviewStatus
from app.services.sync import (
    SyncService,
    count_extras,
    count_products,
    map_payment_type,
    map_record_to_visit_dict,
    map_visit_status,
    parse_comment_date,
    rubles_to_kopecks,
)

# --- Fixtures ---


@pytest.fixture
def org_id():
    return uuid.uuid4()


@pytest.fixture
def branch_id():
    return uuid.uuid4()


@pytest.fixture
def barber_id():
    return uuid.uuid4()


@pytest.fixture
def client_id():
    return uuid.uuid4()


@pytest.fixture
def sample_record():
    """A YClientRecord with 2 services, 1 product, 1 client."""
    return YClientRecord(
        id=1001,
        company_id=555,
        staff_id=10,
        client=YClientRecordClient(id=200, name="Иван Петров", phone="+79001234567"),
        date="2024-10-13",
        services=[
            YClientService(id=1, title="Стрижка", cost=1500.0, first_cost=1500.0, amount=1),
            YClientService(id=2, title="Воск", cost=300.0, first_cost=300.0, amount=1),
        ],
        goods_transactions=[
            YClientGoodsTransaction(id=50, title="Шампунь", cost=800.0, amount=1, good_id=100),
        ],
        cost=2600.0,
        paid_full=1,
        visit_attendance=1,
        attendance=1,
    )


@pytest.fixture
def record_no_client():
    """A record without a client."""
    return YClientRecord(
        id=1002,
        company_id=555,
        staff_id=11,
        client=None,
        date="2024-10-14",
        services=[
            YClientService(id=3, title="Бритьё", cost=1000.0, first_cost=1000.0, amount=1),
        ],
        goods_transactions=[],
        cost=1000.0,
        paid_full=2,
        visit_attendance=1,
        attendance=1,
    )


@pytest.fixture
def record_multiple_products():
    """A record with multiple product quantities."""
    return YClientRecord(
        id=1003,
        company_id=555,
        staff_id=10,
        date="2024-10-15",
        services=[
            YClientService(id=1, title="Стрижка", cost=1500.0),
        ],
        goods_transactions=[
            YClientGoodsTransaction(id=50, title="Шампунь", cost=800.0, amount=2, good_id=100),
            YClientGoodsTransaction(
                id=51, title="Воск для укладки", cost=500.0, amount=3, good_id=101
            ),
        ],
        cost=4800.0,
        paid_full=1,
        visit_attendance=1,
    )


# --- Tests: rubles_to_kopecks ---


class TestRublesToKopecks:
    def test_integer_amount(self):
        assert rubles_to_kopecks(1500) == 150000

    def test_float_amount(self):
        assert rubles_to_kopecks(1500.50) == 150050

    def test_zero(self):
        assert rubles_to_kopecks(0) == 0

    def test_fractional_kopecks(self):
        """Rounding to nearest kopeck."""
        assert rubles_to_kopecks(99.999) == 10000
        assert rubles_to_kopecks(99.991) == 9999

    def test_small_amount(self):
        assert rubles_to_kopecks(0.01) == 1


# --- Tests: map_payment_type ---


class TestMapPaymentType:
    @pytest.mark.parametrize(
        ("paid_full", "expected"),
        [
            (0, "card"),
            (1, "card"),
            (2, "cash"),
            (3, "card"),
            (4, "certificate"),
            (6, "qr"),
        ],
    )
    def test_known_types(self, paid_full, expected):
        assert map_payment_type(paid_full) == expected

    def test_unknown_defaults_to_card(self):
        assert map_payment_type(99) == "card"
        assert map_payment_type(-1) == "card"


# --- Tests: map_visit_status ---


class TestMapVisitStatus:
    @pytest.mark.parametrize(
        ("attendance", "expected"),
        [
            (1, "completed"),
            (2, "scheduled"),
            (-1, "no_show"),
            (0, "scheduled"),
        ],
    )
    def test_known_statuses(self, attendance, expected):
        assert map_visit_status(attendance) == expected

    def test_unknown_defaults_to_scheduled(self):
        """Unknown attendance codes must never silently count as revenue."""
        assert map_visit_status(99) == "scheduled"


# --- Tests: count_extras ---


class TestCountExtras:
    def test_no_extras_configured(self):
        services = [{"title": "Стрижка"}, {"title": "Воск"}]
        assert count_extras(services, []) == 0

    def test_one_extra_match(self):
        services = [{"title": "Стрижка"}, {"title": "Воск"}]
        assert count_extras(services, ["Воск"]) == 1

    def test_multiple_extras(self):
        services = [
            {"title": "Стрижка"},
            {"title": "Воск"},
            {"title": "Массаж головы"},
        ]
        assert count_extras(services, ["Воск", "Массаж головы"]) == 2

    def test_case_insensitive(self):
        services = [{"title": "ВОСК"}]
        assert count_extras(services, ["воск"]) == 1

    def test_whitespace_trimmed(self):
        services = [{"title": "  Воск  "}]
        assert count_extras(services, [" Воск"]) == 1

    def test_no_match(self):
        services = [{"title": "Стрижка"}]
        assert count_extras(services, ["Воск", "Массаж"]) == 0

    def test_empty_services(self):
        assert count_extras([], ["Воск"]) == 0

    def test_combo_service_substring_matches(self):
        """YClients stores combos as one title — each extras keyword hit = +1."""
        services = [
            {"title": "Мужская стрижка + Оформление бороды + Камуфляж бороды"}
        ]
        assert (
            count_extras(services, ["оформление бороды", "камуфляж бороды"]) == 2
        )

    def test_combo_plus_standalone_extra(self):
        services = [
            {"title": "Мужская стрижка + Оформление бороды"},
            {"title": "Удаление волос"},
        ]
        assert (
            count_extras(services, ["оформление бороды", "удаление волос"]) == 2
        )

    def test_does_not_match_partial_unrelated_word(self):
        """Keywords are phrases, not single words — "бороды" alone is unsafe."""
        services = [{"title": "Мужская стрижка"}]
        assert count_extras(services, ["оформление бороды"]) == 0


# --- Tests: count_products ---


class TestCountProducts:
    def test_single_product(self):
        goods = [{"id": 1, "title": "Шампунь", "cost": 800, "amount": 1}]
        assert count_products(goods) == 1

    def test_multiple_products(self):
        goods = [
            {"id": 1, "title": "Шампунь", "cost": 800, "amount": 2},
            {"id": 2, "title": "Воск", "cost": 500, "amount": 3},
        ]
        assert count_products(goods) == 5

    def test_empty_list(self):
        assert count_products([]) == 0

    def test_missing_amount_defaults_to_1(self):
        goods = [{"id": 1, "title": "Шампунь"}]
        assert count_products(goods) == 1


# --- Tests: map_record_to_visit_dict ---


class TestMapRecordToVisitDict:
    def test_basic_mapping(self, sample_record, org_id, branch_id, barber_id, client_id):
        result = map_record_to_visit_dict(
            record=sample_record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )

        assert result["organization_id"] == org_id
        assert result["branch_id"] == branch_id
        assert result["barber_id"] == barber_id
        assert result["client_id"] == client_id
        assert result["yclients_record_id"] == 1001
        assert result["date"] == date(2024, 10, 13)
        assert result["revenue"] == 260000  # 2600 * 100
        assert result["services_revenue"] == 180000  # (1500 + 300) * 100
        assert result["products_revenue"] == 80000  # 800 * 1 * 100
        assert result["payment_type"] == "card"
        assert result["status"] == "completed"

    def test_product_return_does_not_erode_revenue(
        self, org_id, branch_id, barber_id, client_id
    ):
        """A product return must not reduce a visit's revenue below its services."""
        record = YClientRecord(
            id=4001,
            company_id=555,
            staff_id=10,
            date="2026-06-14 12:00:00",
            services=[YClientService(id=1, title="Стрижка", cost=630.0)],
            goods_transactions=[
                YClientGoodsTransaction(
                    id=99, title="Возврат косметики", cost=3990.0, amount=-1, good_id=200
                ),
            ],
            cost=-3360.0,  # YClients net total (haircut minus the return)
            paid_full=1,
            visit_attendance=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )
        assert result["products_revenue"] == 0  # return excluded from revenue
        assert result["revenue"] == 63000  # 630 RUB haircut, never negative
        assert result["products_count"] == 0  # returns don't count as sold

    def test_confirmed_flag_mapped(self, org_id, branch_id, barber_id, client_id):
        """YClients `confirmed` flag (upcoming bookings) maps to Visit.confirmed."""
        record = YClientRecord(
            id=3001,
            company_id=555,
            staff_id=10,
            date="2026-06-10 12:00:00",
            services=[YClientService(id=1, title="Стрижка", cost=1500.0)],
            goods_transactions=[],
            cost=1500.0,
            paid_full=1,
            visit_attendance=0,  # upcoming booking (waiting)
            confirmed=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )
        assert result["confirmed"] is True
        assert result["status"] == "scheduled"  # visit_attendance 0 -> upcoming

    def test_unconfirmed_defaults_false(self, org_id, branch_id, barber_id, client_id):
        """Missing/zero confirmed flag maps to False."""
        record = YClientRecord(
            id=3002,
            company_id=555,
            staff_id=10,
            date="2026-06-10 12:00:00",
            services=[YClientService(id=1, title="Стрижка", cost=1500.0)],
            goods_transactions=[],
            cost=1500.0,
            paid_full=1,
            visit_attendance=0,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )
        assert result["confirmed"] is False

    def test_date_with_time_component_uses_local_date(
        self, org_id, branch_id, barber_id, client_id
    ):
        """A YClients datetime string is bucketed by its local date.

        Guards against timezone drift: a visit late on the 31st (salon-local
        time) must land on the 31st, not roll into the next day/month via a
        UTC conversion. ``map_record_to_visit_dict`` takes ``record.date[:10]``
        as-is, so the local date is preserved.
        """
        record = YClientRecord(
            id=2001,
            company_id=555,
            staff_id=10,
            date="2026-01-31 23:30:00",
            services=[YClientService(id=1, title="Стрижка", cost=1500.0)],
            goods_transactions=[],
            cost=1500.0,
            paid_full=1,
            visit_attendance=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )
        assert result["date"] == date(2026, 1, 31)

    def test_record_cost_zero_falls_back_to_services_plus_products(
        self, org_id, branch_id, barber_id, client_id
    ):
        """When YClients reports cost=0 (unsettled), revenue = services + products."""
        record = YClientRecord(
            id=2002,
            company_id=555,
            staff_id=10,
            date="2026-01-15",
            services=[YClientService(id=1, title="Стрижка", cost=1500.0)],
            goods_transactions=[
                YClientGoodsTransaction(id=50, title="Гель", cost=400.0, amount=2, good_id=1)
            ],
            cost=0.0,
            paid_full=1,
            visit_attendance=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )
        # services 1500*100 + products 400*2*100 = 150000 + 80000
        assert result["services_revenue"] == 150000
        assert result["products_revenue"] == 80000
        assert result["revenue"] == 230000

    def test_services_revenue_sums_then_rounds_once(
        self, org_id, branch_id, barber_id, client_id
    ):
        """Service costs are summed in rubles, then converted to kopecks once.

        Two 0.005₽ services sum to 0.01₽ = 1 kopeck. Rounding each item
        independently (banker's round of 0.5 kopeck -> 0) would yield 0, so
        this proves a single rounding of the summed total.
        """
        record = YClientRecord(
            id=2003,
            company_id=555,
            staff_id=10,
            date="2026-01-15",
            services=[
                YClientService(id=1, title="A", cost=0.005),
                YClientService(id=2, title="B", cost=0.005),
            ],
            goods_transactions=[],
            cost=0.01,
            paid_full=1,
            visit_attendance=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )
        assert result["services_revenue"] == 1

    def test_extras_counted(self, sample_record, org_id, branch_id, barber_id, client_id):
        result = map_record_to_visit_dict(
            record=sample_record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=["Воск"],
        )

        assert result["extras_count"] == 1
        # Verify is_extra flag set in services list
        wax_svc = next(s for s in result["services"] if s["title"] == "Воск")
        assert wax_svc["is_extra"] is True
        # Non-extra should remain False
        cut_svc = next(s for s in result["services"] if s["title"] == "Стрижка")
        assert cut_svc["is_extra"] is False

    def test_products_counted(self, sample_record, org_id, branch_id, barber_id, client_id):
        result = map_record_to_visit_dict(
            record=sample_record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )

        assert result["products_count"] == 1  # 1 product with amount=1

    def test_multiple_products_count(self, record_multiple_products, org_id, branch_id, barber_id):
        result = map_record_to_visit_dict(
            record=record_multiple_products,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=[],
        )

        assert result["products_count"] == 5  # 2 + 3
        assert result["products_revenue"] == 310000  # (800*2 + 500*3) * 100

    def test_no_client(self, record_no_client, org_id, branch_id, barber_id):
        result = map_record_to_visit_dict(
            record=record_no_client,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=[],
        )

        assert result["client_id"] is None
        assert result["products_count"] == 0
        assert result["products_revenue"] == 0

    def test_cash_payment(self, record_no_client, org_id, branch_id, barber_id):
        result = map_record_to_visit_dict(
            record=record_no_client,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=[],
        )

        assert result["payment_type"] == "cash"  # paid_full=2

    def test_services_list_structure(self, sample_record, org_id, branch_id, barber_id, client_id):
        result = map_record_to_visit_dict(
            record=sample_record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )

        assert len(result["services"]) == 2
        svc = result["services"][0]
        assert "id" in svc
        assert "title" in svc
        assert "cost" in svc
        assert "is_extra" in svc

    def test_products_list_structure(self, sample_record, org_id, branch_id, barber_id, client_id):
        result = map_record_to_visit_dict(
            record=sample_record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=client_id,
            extra_services_list=[],
        )

        assert len(result["products"]) == 1
        prod = result["products"][0]
        assert prod["id"] == 50
        assert prod["title"] == "Шампунь"
        assert prod["cost"] == 800.0
        assert prod["amount"] == 1

    def test_confirmed_visit_is_scheduled(self, org_id, branch_id, barber_id):
        """YClients attendance=2 ("confirmed booking") is not yet delivered."""
        record = YClientRecord(
            id=2000,
            staff_id=10,
            date="2024-10-13",
            cost=0,
            visit_attendance=2,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=[],
        )

        assert result["status"] == "scheduled"

    def test_no_show_visit(self, org_id, branch_id, barber_id):
        record = YClientRecord(
            id=2001,
            staff_id=10,
            date="2024-10-13",
            cost=0,
            visit_attendance=-1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=[],
        )

        assert result["status"] == "no_show"

    def test_all_extras_detected(self, org_id, branch_id, barber_id):
        """When all services are extras."""
        record = YClientRecord(
            id=3000,
            staff_id=10,
            date="2024-10-13",
            services=[
                YClientService(id=1, title="Воск", cost=300.0),
                YClientService(id=2, title="Массаж головы", cost=500.0),
            ],
            cost=800.0,
            visit_attendance=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=["Воск", "Массаж головы"],
        )

        assert result["extras_count"] == 2
        assert all(s["is_extra"] for s in result["services"])

    def test_qr_payment(self, org_id, branch_id, barber_id):
        record = YClientRecord(
            id=4000,
            staff_id=10,
            date="2024-10-13",
            cost=1500.0,
            paid_full=6,
            visit_attendance=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=[],
        )

        assert result["payment_type"] == "qr"

    def test_certificate_payment(self, org_id, branch_id, barber_id):
        record = YClientRecord(
            id=4001,
            staff_id=10,
            date="2024-10-13",
            cost=1500.0,
            paid_full=4,
            visit_attendance=1,
        )
        result = map_record_to_visit_dict(
            record=record,
            organization_id=org_id,
            branch_id=branch_id,
            barber_id=barber_id,
            client_id=None,
            extra_services_list=[],
        )

        assert result["payment_type"] == "certificate"


# --- Tests: sync_records savepoint isolation (regression) ---


def _make_savepoint_mock():
    """Return a MagicMock that behaves like `AsyncSessionTransaction` —
    supports `async with` and yields nothing."""
    savepoint = MagicMock()
    savepoint.__aenter__ = AsyncMock(return_value=None)
    savepoint.__aexit__ = AsyncMock(return_value=False)
    return savepoint


def _make_branch_lookup_db(branch_mock, extras_list):
    """Build a mocked `AsyncSession` that answers the two up-front queries in
    `SyncService.sync_records` (branch lookup + RatingConfig.extra_services)
    and supports savepoints via `begin_nested()`.
    """
    branch_result = MagicMock()
    branch_result.scalar_one_or_none.return_value = branch_mock

    extras_result = MagicMock()
    extras_result.scalar_one_or_none.return_value = extras_list

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[branch_result, extras_result])
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.begin_nested = MagicMock(side_effect=_make_savepoint_mock)
    return db


class TestSyncRecordsSavepointIsolation:
    """Regression for the YClients sync incident from 2026-04-01:

    Before the `begin_nested()` fix, a single failing record inside the
    per-record loop left the outer transaction in a failed state. Every
    subsequent record and the final `commit()` then raised
    `PendingRollbackError`, which in turn poisoned the shared session used by
    the polling task for the rest of the cycle.
    """

    @pytest.mark.asyncio
    async def test_one_failing_record_does_not_halt_others(self):
        org_uuid = uuid.uuid4()
        branch_uuid = uuid.uuid4()
        barber_uuid = uuid.uuid4()

        branch_mock = MagicMock()
        branch_mock.id = branch_uuid
        branch_mock.organization_id = org_uuid
        branch_mock.yclients_company_id = 555

        db = _make_branch_lookup_db(branch_mock, extras_list=[])

        # Three records with no nested client (so `_upsert_client` is skipped)
        records = [
            YClientRecord(
                id=1001,
                staff_id=10,
                client=None,
                date="2026-04-08",
                services=[YClientService(id=1, title="A", cost=1000.0)],
                cost=1000.0,
                paid_full=1,
                visit_attendance=1,
            ),
            YClientRecord(
                id=1002,
                staff_id=10,
                client=None,
                date="2026-04-08",
                services=[YClientService(id=1, title="B", cost=1500.0)],
                cost=1500.0,
                paid_full=1,
                visit_attendance=1,
            ),
            YClientRecord(
                id=1003,
                staff_id=10,
                client=None,
                date="2026-04-08",
                services=[YClientService(id=1, title="C", cost=2000.0)],
                cost=2000.0,
                paid_full=1,
                visit_attendance=1,
            ),
        ]

        yclients = MagicMock()
        yclients.get_records = AsyncMock(return_value=records)

        svc = SyncService(db=db, yclients=yclients)

        # Stub internal resolvers so we do not touch the DB for them
        barber = MagicMock()
        barber.id = barber_uuid
        svc._resolve_barber = AsyncMock(return_value=barber)
        svc._upsert_client = AsyncMock(return_value=uuid.uuid4())

        # Second upsert raises — simulating an IntegrityError on a bad row.
        # Without savepoint isolation, this would poison the transaction and
        # `commit()` would also fail.
        svc._upsert_visit = AsyncMock(
            side_effect=[None, RuntimeError("boom: FK or integrity error"), None]
        )

        synced = await svc.sync_records(
            branch_uuid, date(2026, 4, 8), date(2026, 4, 8)
        )

        # All three records were attempted (not halted after the bad one)
        assert svc._upsert_visit.call_count == 3
        # Two succeeded (record 1 and record 3)
        assert synced == 2
        # Final commit still happens (transaction not poisoned)
        db.commit.assert_awaited_once()
        # A savepoint was opened for each record
        assert db.begin_nested.call_count == 3

    @pytest.mark.asyncio
    async def test_barber_not_found_records_are_skipped_not_failed(self):
        """`continue` inside an `async with begin_nested()` must release the
        savepoint cleanly and move on to the next record."""
        org_uuid = uuid.uuid4()
        branch_uuid = uuid.uuid4()

        branch_mock = MagicMock()
        branch_mock.id = branch_uuid
        branch_mock.organization_id = org_uuid
        branch_mock.yclients_company_id = 555

        db = _make_branch_lookup_db(branch_mock, extras_list=[])

        records = [
            YClientRecord(
                id=2001,
                staff_id=111,  # known barber
                client=None,
                date="2026-04-08",
                services=[YClientService(id=1, title="X", cost=1000.0)],
                cost=1000.0,
                visit_attendance=1,
            ),
            YClientRecord(
                id=2002,
                staff_id=222,  # unknown barber — will be skipped
                client=None,
                date="2026-04-08",
                services=[YClientService(id=1, title="Y", cost=1200.0)],
                cost=1200.0,
                visit_attendance=1,
            ),
            YClientRecord(
                id=2003,
                staff_id=111,  # known barber
                client=None,
                date="2026-04-08",
                services=[YClientService(id=1, title="Z", cost=1500.0)],
                cost=1500.0,
                visit_attendance=1,
            ),
        ]

        yclients = MagicMock()
        yclients.get_records = AsyncMock(return_value=records)

        svc = SyncService(db=db, yclients=yclients)

        known_barber = MagicMock()
        known_barber.id = uuid.uuid4()

        def resolve_side_effect(staff_id, _org):
            return known_barber if staff_id == 111 else None

        svc._resolve_barber = AsyncMock(side_effect=resolve_side_effect)
        svc._upsert_visit = AsyncMock(return_value=None)

        synced = await svc.sync_records(
            branch_uuid, date(2026, 4, 8), date(2026, 4, 8)
        )

        # Only 2 records had a resolvable barber
        assert synced == 2
        assert svc._upsert_visit.call_count == 2
        # Commit succeeds — skipped record did not leave the transaction dirty
        db.commit.assert_awaited_once()


# --- Tests: parse_comment_date ---


class TestParseCommentDate:
    def test_valid_datetime_is_msk_aware(self):
        dt = parse_comment_date("2026-05-31 14:33:48")
        assert dt is not None
        assert (dt.year, dt.month, dt.day, dt.hour) == (2026, 5, 31, 14)
        assert dt.utcoffset() == timedelta(hours=3)  # Moscow time

    def test_empty_returns_none(self):
        assert parse_comment_date("") is None

    def test_malformed_returns_none(self):
        assert parse_comment_date("not-a-date") is None


# --- Tests: sync_reviews ---


def _make_review_db(branch_mock, after_branch_results):
    """Mocked AsyncSession for sync_reviews: answers the branch lookup, then the
    given per-comment query results, and supports savepoints via begin_nested.
    """
    branch_result = MagicMock()
    branch_result.scalar_one_or_none.return_value = branch_mock

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[branch_result, *after_branch_results])
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.begin_nested = MagicMock(side_effect=_make_savepoint_mock)
    return db


def _exists_result(found):
    r = MagicMock()
    r.scalar_one_or_none.return_value = found
    return r


def _visit_row_result(row):
    r = MagicMock()
    r.first.return_value = row
    return r


class TestSyncReviews:
    @pytest.mark.asyncio
    async def test_maps_and_routes_reviews(self):
        org_uuid = uuid.uuid4()
        branch_uuid = uuid.uuid4()

        branch_mock = MagicMock()
        branch_mock.id = branch_uuid
        branch_mock.organization_id = org_uuid
        branch_mock.yclients_company_id = 555

        comments = [
            YClientComment(id=901, salon_id=555, master_id=10, record_id=0, rating=2, text="плохо"),
            YClientComment(id=902, salon_id=555, master_id=10, record_id=0, rating=5, text=""),
            YClientComment(id=903, salon_id=555, master_id=10, record_id=0, rating=0),  # not a star
            YClientComment(id=904, salon_id=555, master_id=999, record_id=0, rating=4),  # no barber
        ]

        # execute order after branch: existence checks for 901, 902, 904
        # (903 is filtered out before any query; no visit lookups since record_id=0)
        db = _make_review_db(
            branch_mock,
            [_exists_result(None), _exists_result(None), _exists_result(None)],
        )

        yclients = MagicMock()
        yclients.get_comments = AsyncMock(return_value=comments)

        svc = SyncService(db=db, yclients=yclients)
        barber = MagicMock()
        barber.id = uuid.uuid4()
        svc._resolve_barber = AsyncMock(
            side_effect=lambda master_id, _org: barber if master_id == 10 else None
        )

        inserted = await svc.sync_reviews(branch_uuid)

        assert inserted == 2  # 901 (negative) and 902 (positive); 903/904 skipped
        added = [c.args[0] for c in db.add.call_args_list]
        assert len(added) == 2
        negative, positive = added
        assert negative.rating == 2
        assert negative.status == ReviewStatus.NEW
        assert negative.source == "yclients"
        assert negative.yclients_comment_id == 901
        assert negative.comment == "плохо"
        assert positive.rating == 5
        assert positive.status == ReviewStatus.PROCESSED
        assert positive.comment is None  # empty text -> None
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_idempotent_skips_already_synced(self):
        org_uuid = uuid.uuid4()
        branch_uuid = uuid.uuid4()
        branch_mock = MagicMock()
        branch_mock.id = branch_uuid
        branch_mock.organization_id = org_uuid
        branch_mock.yclients_company_id = 555

        comments = [YClientComment(id=901, salon_id=555, master_id=10, record_id=0, rating=2)]
        # existence check returns an existing review id -> skip
        db = _make_review_db(branch_mock, [_exists_result(uuid.uuid4())])

        yclients = MagicMock()
        yclients.get_comments = AsyncMock(return_value=comments)

        svc = SyncService(db=db, yclients=yclients)
        svc._resolve_barber = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

        inserted = await svc.sync_reviews(branch_uuid)

        assert inserted == 0
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_links_visit_and_client_from_record(self):
        org_uuid = uuid.uuid4()
        branch_uuid = uuid.uuid4()
        visit_uuid = uuid.uuid4()
        client_uuid = uuid.uuid4()
        branch_mock = MagicMock()
        branch_mock.id = branch_uuid
        branch_mock.organization_id = org_uuid
        branch_mock.yclients_company_id = 555

        comments = [
            YClientComment(id=901, salon_id=555, master_id=10, record_id=777, rating=3)
        ]
        # after branch: existence check (None), then visit lookup -> (visit, client)
        db = _make_review_db(
            branch_mock,
            [_exists_result(None), _visit_row_result((visit_uuid, client_uuid))],
        )

        yclients = MagicMock()
        yclients.get_comments = AsyncMock(return_value=comments)

        svc = SyncService(db=db, yclients=yclients)
        svc._resolve_barber = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

        inserted = await svc.sync_reviews(branch_uuid)

        assert inserted == 1
        review = db.add.call_args_list[0].args[0]
        assert review.visit_id == visit_uuid
        assert review.client_id == client_uuid
        assert review.status == ReviewStatus.NEW  # rating 3 is negative

    @staticmethod
    def _msk_date_str(hours_ago: int) -> str:
        """A YClients-style salon-local (MSK) date string N hours before now."""
        msk = timezone(timedelta(hours=3))
        dt = datetime.now(UTC).astimezone(msk) - timedelta(hours=hours_ago)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _negative_branch(self):
        branch = MagicMock()
        branch.id = uuid.uuid4()
        branch.organization_id = uuid.uuid4()
        branch.yclients_company_id = 555
        branch.name = "Test Branch"
        return branch

    async def _run_sync_one_negative(self, date_str):
        branch = self._negative_branch()
        comments = [
            YClientComment(
                id=950, salon_id=555, master_id=10, record_id=0, rating=2,
                text="bad", date=date_str,
            )
        ]
        db = _make_review_db(branch, [_exists_result(None)])
        yclients = MagicMock()
        yclients.get_comments = AsyncMock(return_value=comments)
        svc = SyncService(db=db, yclients=yclients)
        svc._resolve_barber = AsyncMock(return_value=MagicMock(id=uuid.uuid4(), name="Pavel"))
        with patch("app.tasks.notification_tasks.send_negative_review_alert") as mock_task:
            inserted = await svc.sync_reviews(branch.id)
        return inserted, mock_task

    @pytest.mark.asyncio
    async def test_alerts_for_fresh_negative(self):
        """A negative review created within 48h queues a Telegram alert."""
        inserted, mock_task = await self._run_sync_one_negative(self._msk_date_str(1))
        assert inserted == 1
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_alert_for_old_negative(self):
        """An old (backfilled) negative is stored but does NOT alert."""
        inserted, mock_task = await self._run_sync_one_negative(self._msk_date_str(100))
        assert inserted == 1
        mock_task.delay.assert_not_called()
