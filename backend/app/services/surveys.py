"""Guest-survey (Yandex Forms) ingestion: parse, score, store.

The Yandex Form posts a flat JSON of answers (keys defined in
docs/modules/admin-module.md). We store the whole payload (`raw`) and extract a
curated set of fields, compute an admin and master score (0-100), flag negative
feedback, and resolve branch (by text) / client (by phone) / barber (by the
client's most recent visit at that branch).
"""

import re
import uuid

import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.client import Client
from app.models.survey_response import SurveyResponse
from app.models.visit import Visit

logger = structlog.stdlib.get_logger()

# Admin-communication answer (4 levels) -> 0-100.
# Order matters: more specific phrases first ("very bad" before "bad").
_ADMIN_COMM_SCORE = {
    "очень плохо": 0,
    "плохо": 33,
    "нормально": 66,
    "хорошо": 100,
}

# Haircut-quality answer (6 levels) -> 0-100.
_QUALITY_SCORE = [
    ("превзошла", 100),
    ("полностью устроила", 85),
    ("устранил", 70),
    ("могло быть лучше", 50),
    ("не понравилась", 25),
    ("ужасно", 0),
]

# "Would you return to this master?" -> 0-100.
_RETURN_SCORE = {"да": 100, "не уверен": 50, "нет": 0}

# Admin yes/no checklist fields (sections 1 and 3 of the survey).
_ADMIN_CHECKLIST = (
    "admin_greeting",
    "admin_amenities",
    "admin_drinks",
    "admin_staff_greeting",
    "admin_next_visit",
    "admin_promo",
)


def _branch_matches(survey_text_low: str, branch_name: str) -> bool:
    """Match a survey branch label to a DB branch name across scripts.

    The survey sends Cyrillic ("Менделеева 17Б"), the DB name is Latin
    ("MAKON - Mendeleeva 17B"), so we match on the street number (distinct
    across MAKON branches) and, as a fallback, any shared word (same script).
    """
    name = branch_name.lower()
    numbers = re.findall(r"\d+", name)
    if any(n in survey_text_low for n in numbers):
        return True
    for token in re.findall(r"[a-zа-яё]{5,}", name):
        if token != "makon" and token in survey_text_low:
            return True
    return False


def phone_digits(value: str | None) -> str:
    """Digits-only phone; Russian leading 8 -> 7. '' if too short."""
    if not value:
        return ""
    d = "".join(ch for ch in str(value) if ch.isdigit())
    if len(d) == 11 and d.startswith("8"):
        d = "7" + d[1:]
    return d if len(d) >= 10 else ""


def _is_yes(value: str | None) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip().lower().startswith("да")


def _score_from_text(value: str | None, mapping: dict[str, int]) -> int | None:
    if not value:
        return None
    low = str(value).strip().lower()
    for key, score in mapping.items():
        if low.startswith(key) or key in low:
            return score
    return None


def _quality_score(value: str | None) -> int | None:
    if not value:
        return None
    low = str(value).lower()
    for needle, score in _QUALITY_SCORE:
        if needle in low:
            return score
    return None


def _parse_stars(value) -> int | None:
    """Stars may arrive as '5', '★★★★★', or 'Оценка 5'."""
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 5 else None
    s = str(value)
    stars = s.count("★")
    if 1 <= stars <= 5:
        return stars
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        n = int(digits[0])
        return n if 1 <= n <= 5 else None
    return None


def compute_admin_score(payload: dict) -> int | None:
    """0-100 from admin communication (Q23) + the yes/no admin checklist."""
    comm = _score_from_text(payload.get("admin_communication"), _ADMIN_COMM_SCORE)
    checks = [_is_yes(payload.get(k)) for k in _ADMIN_CHECKLIST]
    checks = [c for c in checks if c is not None]
    checklist = round(sum(checks) / len(checks) * 100) if checks else None

    parts = [p for p in (comm, checklist) if p is not None]
    if not parts:
        return None
    if comm is not None and checklist is not None:
        return round(0.5 * comm + 0.5 * checklist)
    return parts[0]


def compute_master_score(payload: dict) -> int | None:
    """0-100 from cut quality (Q18) + return-to-master (Q19)."""
    quality = _quality_score(payload.get("master_quality"))
    ret = _score_from_text(payload.get("master_return"), _RETURN_SCORE)
    if quality is not None and ret is not None:
        return round(0.6 * quality + 0.4 * ret)
    return quality if quality is not None else ret


def is_negative(payload: dict, stars: int | None) -> bool:
    """A survey is negative if any strong dissatisfaction signal is present."""
    if stars is not None and stars <= 2:
        return True
    rec = _is_yes(payload.get("recommend"))
    if rec is False:
        return True
    comm = (payload.get("admin_communication") or "").lower()
    if comm.startswith("плохо") or comm.startswith("очень плохо"):
        return True
    quality = (payload.get("master_quality") or "").lower()
    return "не понравилась" in quality or "ужасно" in quality


def _extract_answer_value(value, answer_type: str) -> str:
    """Reduce one Yandex answer `value` to a plain string by its type.

    - boolean -> "Да"/"Нет"
    - choices (single/matrix) -> selected option text (matrix: the column text)
    - short text / number -> the value as string
    """
    if answer_type == "answer_boolean":
        if value is True:
            return "Да"
        if value is False:
            return "Нет"
        return ""
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            col = first.get("col")
            if isinstance(col, dict):  # matrix (e.g. stars)
                return col.get("text") or ""
            return first.get("text") or ""
        return str(first)
    if isinstance(value, str | int | float):
        return str(value)
    return ""


def flatten_yandex_answers(payload: dict) -> dict | None:
    """Flatten the Yandex Forms "Ответы на вопросы в виде json" payload.

    Shape: ``{"answer": {"data": {"<slug>": {"value": ..., "question": {...}}}}}``.
    Returns ``{slug: plain_value}`` or None if the payload isn't that format.
    """
    data = (payload.get("answer") or {}).get("data")
    if not isinstance(data, dict):
        return None
    flat: dict[str, str] = {}
    for slug, entry in data.items():
        if not isinstance(entry, dict):
            continue
        answer_type = ((entry.get("question") or {}).get("answer_type") or {}).get("slug", "")
        flat[slug] = _extract_answer_value(entry.get("value"), answer_type)
    return flat


class SurveyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def parse_and_store(self, payload: dict) -> SurveyResponse | None:
        """Parse a guest-survey payload, resolve relations, score, and store.

        Accepts either a flat ``{key: value}`` payload or the nested Yandex
        "Ответы на вопросы в виде json" shape (flattened here). The original
        payload is preserved in ``raw``.
        """
        answers = flatten_yandex_answers(payload) or payload

        branch, organization_id = await self._resolve_branch_and_org(answers.get("branch"))
        if organization_id is None:
            await logger.awarning("Survey: could not resolve organization", branch=answers.get("branch"))
            return None
        branch_id = branch.id if branch else None

        phone = phone_digits(answers.get("phone"))
        client = await self._resolve_client(organization_id, phone) if phone else None
        client_id = client.id if client else None

        barber_id = None
        if client_id and branch_id:
            barber_id = await self._resolve_last_barber(branch_id, client_id)

        stars = _parse_stars(answers.get("stars"))
        survey = SurveyResponse(
            id=uuid.uuid4(),
            organization_id=organization_id,
            branch_id=branch_id,
            client_id=client_id,
            barber_id=barber_id,
            phone=answers.get("phone") or "",
            recommend=_is_yes(answers.get("recommend")),
            stars=stars,
            comment=(answers.get("comment") or "").strip() or None,
            admin_score=compute_admin_score(answers),
            master_score=compute_master_score(answers),
            is_negative=is_negative(answers, stars),
            raw=payload,
        )
        self.db.add(survey)
        await self.db.commit()

        await logger.ainfo(
            "Survey stored",
            branch_id=str(branch_id) if branch_id else None,
            stars=stars,
            admin_score=survey.admin_score,
            negative=survey.is_negative,
        )
        return survey

    async def _resolve_branch_and_org(
        self, branch_text: str | None
    ) -> tuple[Branch | None, uuid.UUID | None]:
        result = await self.db.execute(select(Branch).order_by(Branch.name))
        branches = list(result.scalars().all())
        if not branches:
            return None, None
        if branch_text:
            low = branch_text.lower()
            for b in branches:
                if _branch_matches(low, b.name or ""):
                    return b, b.organization_id
        # Fallback: single-tenant deployment — attribute to the first branch's org.
        return None, branches[0].organization_id

    async def _resolve_client(self, organization_id: uuid.UUID, phone: str) -> Client | None:
        # Match by digits-only suffix to tolerate stored formatting differences.
        result = await self.db.execute(
            select(Client).where(
                Client.organization_id == organization_id,
                sa_func.regexp_replace(Client.phone, r"\D", "", "g").like(f"%{phone}"),
            )
        )
        return result.scalars().first()

    async def _resolve_last_barber(
        self, branch_id: uuid.UUID, client_id: uuid.UUID
    ) -> uuid.UUID | None:
        result = await self.db.execute(
            select(Visit.barber_id)
            .where(
                Visit.branch_id == branch_id,
                Visit.client_id == client_id,
                Visit.status == "completed",
            )
            .order_by(Visit.date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
