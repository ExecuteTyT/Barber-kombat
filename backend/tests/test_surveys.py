"""Tests for guest-survey (Yandex Forms) parsing, scoring, and webhook."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services.surveys import (
    SurveyService,
    _branch_matches,
    compute_admin_score,
    compute_master_score,
    flatten_yandex_answers,
    is_negative,
    phone_digits,
)

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
CLIENT_ID = uuid.uuid4()
BARBER_ID = uuid.uuid4()


# --- Scoring helpers ---


class TestPhoneDigits:
    def test_russian_eight_normalised(self):
        assert phone_digits("8 (917) 854-91-77") == "79178549177"

    def test_plus_seven(self):
        assert phone_digits("+7 999 123-45-67") == "79991234567"

    def test_too_short(self):
        assert phone_digits("12345") == ""

    def test_empty(self):
        assert phone_digits(None) == ""


class TestBranchMatches:
    def test_cyrillic_survey_to_latin_db_by_number(self):
        # Survey is Cyrillic, DB name is Latin — match on the street number.
        assert _branch_matches('менделеева 17б (тц "аяз")', "MAKON - Mendeleeva 17B") is True
        assert _branch_matches('корабельная 53 (тц "парус")', "MAKON - Korabelnaya 53") is True

    def test_does_not_cross_match(self):
        assert _branch_matches('корабельная 53 (тц "парус")', "MAKON - Mendeleeva 17B") is False


class TestAdminScore:
    def test_excellent(self):
        payload = {
            "admin_communication": "Хорошо: дружелюбно и внимательно",
            "admin_greeting": "Да",
            "admin_amenities": "Да",
            "admin_drinks": "Да",
            "admin_staff_greeting": "Да",
            "admin_next_visit": "Да",
            "admin_promo": "Да",
        }
        assert compute_admin_score(payload) == 100

    def test_poor_communication_partial_checklist(self):
        payload = {
            "admin_communication": "Очень плохо: недружелюбно и резко",
            "admin_greeting": "Нет",
            "admin_drinks": "Да",
        }
        # comm=0, checklist = 1/2*100=50 -> round(0.5*0 + 0.5*50)=25
        assert compute_admin_score(payload) == 25

    def test_only_communication(self):
        assert compute_admin_score({"admin_communication": "Нормально: вежливо, но сухо"}) == 66

    def test_none_when_absent(self):
        assert compute_admin_score({}) is None


class TestMasterScore:
    def test_quality_and_return(self):
        payload = {"master_quality": "Стрижка меня полностью устроила", "master_return": "Да"}
        # quality=85, return=100 -> round(0.6*85+0.4*100)=91
        assert compute_master_score(payload) == 91

    def test_quality_only(self):
        assert compute_master_score({"master_quality": "Стрижка превзошла мои ожидания"}) == 100

    def test_none_when_absent(self):
        assert compute_master_score({}) is None


class TestIsNegative:
    def test_low_stars(self):
        assert is_negative({}, 2) is True

    def test_not_recommend(self):
        assert is_negative({"recommend": "Нет, не порекомендую"}, 5) is True

    def test_poor_admin(self):
        assert is_negative({"admin_communication": "Плохо: безразлично"}, 4) is True

    def test_bad_quality(self):
        assert is_negative({"master_quality": "Ужасно, нужно перестригаться"}, 4) is True

    def test_all_good(self):
        payload = {"recommend": "Да, порекомендую", "admin_communication": "Хорошо"}
        assert is_negative(payload, 5) is False


class TestFlattenYandexAnswers:
    def test_flattens_nested_answers_by_type(self):
        payload = {
            "answer": {
                "data": {
                    "phone": {
                        "value": "9999999999",
                        "question": {"answer_type": {"slug": "answer_short_text"}},
                    },
                    "recommend": {
                        "value": True,
                        "question": {"answer_type": {"slug": "answer_boolean"}},
                    },
                    "branch": {
                        "value": [{"text": "Менделеева 17Б (ТЦ Аяз)"}],
                        "question": {"answer_type": {"slug": "answer_choices"}},
                    },
                    "master_quality": {
                        "value": [{"text": "1 превзошла"}],
                        "question": {"answer_type": {"slug": "answer_choices"}},
                    },
                    "stars": {
                        "value": [{"col": {"text": "4"}, "row": {}}],
                        "question": {"answer_type": {"slug": "answer_choices"}},
                    },
                }
            }
        }
        flat = flatten_yandex_answers(payload)
        assert flat["phone"] == "9999999999"
        assert flat["recommend"] == "Да"
        assert flat["branch"] == "Менделеева 17Б (ТЦ Аяз)"
        assert flat["master_quality"] == "1 превзошла"
        assert flat["stars"] == "4"  # matrix -> column text

    def test_returns_none_for_flat_payload(self):
        assert flatten_yandex_answers({"phone": "x"}) is None


# --- SurveyService.parse_and_store ---


class TestParseAndStore:
    @pytest.mark.asyncio
    async def test_builds_scored_response(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        svc = SurveyService(db=db)

        branch = MagicMock()
        branch.id = BRANCH_ID
        branch.organization_id = ORG_ID
        client = MagicMock()
        client.id = CLIENT_ID
        svc._resolve_branch_and_org = AsyncMock(return_value=(branch, ORG_ID))
        svc._resolve_client = AsyncMock(return_value=client)
        svc._resolve_last_barber = AsyncMock(return_value=BARBER_ID)

        payload = {
            "phone": "+7 917 854-91-77",
            "branch": 'Менделеева 17Б (ТЦ "Аяз")',
            "stars": "★★★★★",
            "recommend": "Да, порекомендую",
            "comment": "Всё отлично",
            "admin_communication": "Хорошо: дружелюбно и внимательно",
            "admin_greeting": "Да",
            "admin_drinks": "Да",
            "master_quality": "Стрижка меня полностью устроила",
            "master_return": "Да",
        }

        await svc.parse_and_store(payload)

        db.add.assert_called_once()
        survey = db.add.call_args.args[0]
        assert survey.organization_id == ORG_ID
        assert survey.branch_id == BRANCH_ID
        assert survey.client_id == CLIENT_ID
        assert survey.barber_id == BARBER_ID
        assert survey.stars == 5
        assert survey.recommend is True
        assert survey.admin_score == 100
        assert survey.master_score == 91
        assert survey.is_negative is False
        assert survey.raw == payload
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parses_nested_yandex_payload(self):
        """End-to-end: the nested 'answers json' shape is flattened and scored."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        svc = SurveyService(db=db)
        branch = MagicMock()
        branch.id = BRANCH_ID
        branch.organization_id = ORG_ID
        svc._resolve_branch_and_org = AsyncMock(return_value=(branch, ORG_ID))
        svc._resolve_client = AsyncMock(return_value=None)
        svc._resolve_last_barber = AsyncMock(return_value=None)

        def q(slug):
            return {"answer_type": {"slug": slug}}

        payload = {
            "answer": {
                "data": {
                    "phone": {"value": "9999999999", "question": q("answer_short_text")},
                    "branch": {"value": [{"text": "Менделеева 17Б"}], "question": q("answer_choices")},
                    "admin_communication": {
                        "value": [{"text": "Хорошо: дружелюбно и внимательно"}],
                        "question": q("answer_choices"),
                    },
                    "admin_greeting": {"value": True, "question": q("answer_boolean")},
                    "master_quality": {
                        "value": [{"text": "Стрижка превзошла мои ожидания"}],
                        "question": q("answer_choices"),
                    },
                    "master_return": {"value": True, "question": q("answer_boolean")},
                    "stars": {"value": [{"col": {"text": "5"}}], "question": q("answer_choices")},
                    "recommend": {"value": True, "question": q("answer_boolean")},
                }
            }
        }

        await svc.parse_and_store(payload)

        s = db.add.call_args.args[0]
        assert s.stars == 5
        assert s.recommend is True
        assert s.admin_score == 100  # comm 100 + checklist 100
        assert s.master_score == 100  # quality 100 + return 100
        assert s.is_negative is False
        assert s.raw == payload  # original nested payload preserved

    @pytest.mark.asyncio
    async def test_no_org_returns_none(self):
        db = AsyncMock()
        db.add = MagicMock()
        svc = SurveyService(db=db)
        svc._resolve_branch_and_org = AsyncMock(return_value=(None, None))

        result = await svc.parse_and_store({"branch": "Unknown"})

        assert result is None
        db.add.assert_not_called()


# --- Webhook endpoint auth ---


class TestYandexFormsWebhook:
    @pytest.fixture(autouse=True)
    def _override_db(self):
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_bad_secret_rejected(self):
        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.yandex_forms_secret = "right-secret"
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/webhooks/yandex-forms",
                    json={"secret": "wrong", "branch": "Менделеева"},
                )
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    @pytest.mark.asyncio
    async def test_jsonrpc_params_unwrapped(self):
        """JSON-RPC mode wraps answers in `params` — they must be flattened."""
        with (
            patch("app.api.webhooks.settings") as mock_settings,
            patch(
                "app.api.webhooks.SurveyService.parse_and_store",
                new_callable=AsyncMock,
            ) as mock_store,
        ):
            mock_settings.yandex_forms_secret = "right-secret"
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/webhooks/yandex-forms",
                    headers={"X-Survey-Secret": "right-secret"},
                    json={
                        "jsonrpc": "2.0",
                        "method": "survey",
                        "params": {"branch": "Менделеева", "stars": "5"},
                        "id": 1,
                    },
                )
        assert resp.json()["ok"] is True
        flat = mock_store.call_args.args[0]
        assert flat["branch"] == "Менделеева"
        assert flat["stars"] == "5"

    @pytest.mark.asyncio
    async def test_good_secret_processed(self):
        with (
            patch("app.api.webhooks.settings") as mock_settings,
            patch(
                "app.api.webhooks.SurveyService.parse_and_store",
                new_callable=AsyncMock,
            ) as mock_store,
        ):
            mock_settings.yandex_forms_secret = "right-secret"
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/webhooks/yandex-forms",
                    headers={"X-Survey-Secret": "right-secret"},
                    json={"branch": "Менделеева", "stars": "5"},
                )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_store.assert_awaited_once()
