"""Tests for the DataHeroes BFF client and QC call-task service."""

import base64
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.dataheroes.client import DataHeroesClient, _jwt_sub
from app.integrations.dataheroes.schemas import DHTask
from app.services.admin import AdminService


def _make_jwt(sub: str) -> str:
    """Build an unsigned JWT carrying a `sub` claim (signature is ignored)."""

    def seg(obj: dict) -> str:
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{seg({'alg': 'HS256'})}.{seg({'sub': sub})}.sig"


# JWT whose payload's `sub` matches the real DataHeroes account's user id.
JWT = _make_jwt("auth0|UycEDxcVivWfeodGSbvfB")
BRANCH_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()


def mock_response(json_data, status_code=200):
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("POST", "https://bff.dataheroes.pro/api/x"),
    )


@pytest.fixture
def client():
    return DataHeroesClient(
        email="bot@example.com", password="secret", company="GCB2", max_concurrent=5
    )


# --- JWT helper ---


def test_jwt_sub_decodes_unverified():
    assert _jwt_sub(JWT) == "auth0|UycEDxcVivWfeodGSbvfB"


def test_jwt_sub_bad_token_returns_none():
    assert _jwt_sub("not-a-jwt") is None


# --- Client ---


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_caches_token(self, client):
        http = AsyncMock()
        http.is_closed = False
        http.post = AsyncMock(return_value=mock_response({"error": None, "data": {"token": JWT}}))
        with patch.object(client, "_get_client", AsyncMock(return_value=http)):
            token = await client.login()
        assert token == JWT
        assert client._token == JWT

    @pytest.mark.asyncio
    async def test_login_without_token_raises(self, client):
        http = AsyncMock()
        http.is_closed = False
        http.post = AsyncMock(return_value=mock_response({"data": {}}))
        with (
            patch.object(client, "_get_client", AsyncMock(return_value=http)),
            pytest.raises(RuntimeError),
        ):
            await client.login()


class TestGetQcTasks:
    @pytest.mark.asyncio
    async def test_parses_tasks(self, client):
        client._token = JWT
        payload = {
            "data": [
                {
                    "communicationId": "46053840731",
                    "projectId": "ZSXIHEMPX",
                    "clientId": "412218504",
                    "clientNameWithNum": "Сергей 194",
                    "clientPhone": "+79963367702",
                    "status": "Нужно связаться",
                    "clientVisitCnt": 1,
                    "activationId": 185299,
                    "activationName": "Контроль качества. Был впервые.",
                    "ignoredExtraField": "whatever",
                }
            ]
        }
        http = AsyncMock()
        http.is_closed = False
        http.post = AsyncMock(return_value=mock_response(payload))
        with patch.object(client, "_get_client", AsyncMock(return_value=http)):
            tasks = await client.get_qc_tasks("ZSXIHEMPX")

        assert len(tasks) == 1
        t = tasks[0]
        assert isinstance(t, DHTask)
        assert t.communication_id == "46053840731"
        assert t.client_name_with_num == "Сергей 194"
        assert t.client_phone == "+79963367702"
        assert t.client_visit_cnt == 1
        assert t.activation_name == "Контроль качества. Был впервые."
        # Endpoint and company segment are correct.
        assert http.post.await_args.args[0] == "/GCB2/taskList/getData"


class TestMarkContacted:
    @pytest.mark.asyncio
    async def test_posts_action_with_user_from_token(self, client):
        client._token = JWT
        http = AsyncMock()
        http.is_closed = False
        http.post = AsyncMock(return_value=mock_response({"error": None, "data": {}}))
        with patch.object(client, "_get_client", AsyncMock(return_value=http)):
            await client.mark_contacted(
                communication_id="46053840731",
                project_id="ZSXIHEMPX",
                client_id="412218504",
            )

        path = http.post.await_args.args[0]
        body = http.post.await_args.kwargs["json"]
        assert path == "/GCB2/taskList/action"
        assert body["actionType"] == "CONTACT"
        assert body["communicationId"] == "46053840731"
        assert body["data"]["userId"] == "auth0|UycEDxcVivWfeodGSbvfB"
        assert body["data"]["clientId"] == "412218504"
        assert body["data"]["userName"] == "bot@example.com"

    @pytest.mark.asyncio
    async def test_relogin_on_401(self, client):
        client._token = JWT
        http = AsyncMock()
        http.is_closed = False
        # 1) first action POST -> 401, 2) login POST -> token, 3) retry action -> ok
        http.post = AsyncMock(
            side_effect=[
                mock_response({"error": "unauthorized"}, status_code=401),
                mock_response({"data": {"token": JWT}}),
                mock_response({"error": None, "data": {"ok": True}}),
            ]
        )
        with (
            patch.object(client, "_get_client", AsyncMock(return_value=http)),
            patch("app.integrations.dataheroes.client.asyncio.sleep", AsyncMock()),
        ):
            result = await client.mark_contacted("c1", "ZSXIHEMPX")

        assert result == {"error": None, "data": {"ok": True}}
        # login happened between the failed and successful action calls
        assert http.post.await_args_list[1].args[0] == "/auth/login"


# --- Service: QC call list + mark ---


def _dh_row(task_id: str, status: str = "pending"):
    r = MagicMock()
    r.dataheroes_task_id = task_id
    r.client_name = "Сергей 194"
    r.phone = "+79963367702"
    r.reason = "Контроль качества. Был впервые."
    r.visit_count = 1
    r.status = status
    r.result = None
    r.dh_project_id = "ZSXIHEMPX"
    r.dh_client_id = "412218504"
    r.branch_id = BRANCH_ID
    return r


class TestGetQcCallList:
    @pytest.mark.asyncio
    async def test_progress_and_shape(self):
        rows = [_dh_row("a"), _dh_row("b", status="contacted"), _dh_row("c")]
        scalars = MagicMock()
        scalars.scalars.return_value.all.return_value = rows
        db = AsyncMock()
        db.execute = AsyncMock(return_value=scalars)

        data = await AdminService(db=db).get_qc_call_list(BRANCH_ID)

        assert data["total"] == 3
        assert data["contacted_count"] == 1
        assert data["pending_count"] == 2
        assert data["progress"] == 33  # 1/3
        assert data["tasks"][0]["client_name"] == "Сергей 194"


class TestMarkQcCall:
    @pytest.mark.asyncio
    async def test_marks_local_first_no_push_when_disabled(self):
        row = _dh_row("a")
        found = MagicMock()
        found.scalar_one_or_none.return_value = row
        db = AsyncMock()
        db.execute = AsyncMock(return_value=found)
        db.commit = AsyncMock()

        # dataheroes_enabled defaults to False -> push skipped, local mark kept.
        result = await AdminService(db=db).mark_qc_call(
            branch_id=BRANCH_ID, admin_id=ADMIN_ID, task_id="a", result="no_answer"
        )

        assert result == {"ok": True, "pushed": False}
        assert row.status == "contacted"
        assert row.result == "no_answer"
        assert row.contacted_by == ADMIN_ID
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_not_found(self):
        found = MagicMock()
        found.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute = AsyncMock(return_value=found)

        result = await AdminService(db=db).mark_qc_call(
            branch_id=BRANCH_ID, admin_id=ADMIN_ID, task_id="missing"
        )
        assert result == {"ok": False, "error": "not_found"}
