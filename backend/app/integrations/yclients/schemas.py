"""Pydantic models for YClients API responses."""

from pydantic import BaseModel, Field


class YClientService(BaseModel):
    """A service within a visit record."""

    id: int
    title: str = ""
    cost: float = 0
    first_cost: float = 0
    amount: int = 1


class YClientGoodsTransaction(BaseModel):
    """A goods/product sale within a visit record."""

    id: int
    title: str = ""
    cost: float = 0
    amount: int = 1
    good_id: int = 0


class YClientRecordClient(BaseModel):
    """Client info nested in a record."""

    id: int = 0
    name: str = ""
    phone: str = ""


class YClientRecord(BaseModel):
    """A single visit/record from YClients API."""

    id: int
    company_id: int = 0
    staff_id: int = 0
    client: YClientRecordClient | None = None
    date: str = ""  # "YYYY-MM-DD"
    datetime_field: str = Field("", alias="datetime")
    services: list[YClientService] = []
    goods_transactions: list[YClientGoodsTransaction] = []
    cost: float = 0  # total cost
    paid_full: int = 0  # 1 = card, 2 = cash, etc.
    # YClients attendance codes: -1=no-show, 0=waiting, 1=came, 2=confirmed.
    visit_attendance: int = 0
    attendance: int = 0  # alternative attendance field
    confirmed: int = 0  # YClients confirmation flag (1 = client confirmed booking)

    model_config = {"populate_by_name": True}


class YClientStaff(BaseModel):
    """A staff member from YClients API."""

    id: int
    name: str = ""
    specialization: str = ""
    fired: int | bool = 0  # 0 or false = active


class YClientServiceItem(BaseModel):
    """A service definition from YClients API."""

    id: int
    title: str = ""
    category_id: int = 0
    price_min: float = 0
    price_max: float = 0


class YClientClient(BaseModel):
    """A client from YClients API."""

    id: int
    name: str = ""
    phone: str = ""
    birth_date: str = ""  # "YYYY-MM-DD" or ""
    visits_count: int = 0


class YClientComment(BaseModel):
    """A review/comment about the company from YClients API (отзыв).

    Returned by GET /comments/{company_id}. ``rating`` is 1-5; ``text`` may be
    empty for rating-only reviews. ``master_id`` / ``record_id`` link to the
    staff member and visit (0 when absent). ``date`` is salon-local.
    """

    id: int
    salon_id: int = 0
    type: int = 0
    master_id: int = 0
    record_id: int = 0
    rating: int = 0
    text: str = ""
    date: str = ""  # "YYYY-MM-DD HH:MM:SS" (salon-local)
    user_name: str = ""
    user_phone: str = ""
