"""Tests for SyncService mapping helpers and logic."""

import uuid
from datetime import date

import pytest

from app.integrations.yclients.schemas import (
    YClientGoodsTransaction,
    YClientRecord,
    YClientRecordClient,
    YClientService,
)
from app.services.sync import (
    count_extras,
    count_products,
    map_payment_type,
    map_record_to_visit_dict,
    map_visit_status,
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
            (2, "cancelled"),
            (-1, "no_show"),
            (0, "completed"),
        ],
    )
    def test_known_statuses(self, attendance, expected):
        assert map_visit_status(attendance) == expected

    def test_unknown_defaults_to_completed(self):
        assert map_visit_status(99) == "completed"


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

    def test_cancelled_visit(self, org_id, branch_id, barber_id):
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

        assert result["status"] == "cancelled"

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
