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
    visit_attendance: int = 0  # 1=completed, 2=cancelled, -1=no_show
    attendance: int = 0  # alternative attendance field

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
