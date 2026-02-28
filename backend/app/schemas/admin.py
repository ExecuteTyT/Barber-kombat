"""Pydantic schemas for Admin API endpoints."""

from pydantic import BaseModel

# --- Metrics ---


class AdminMetricsResponse(BaseModel):
    """Daily admin metrics for a branch."""

    branch_id: str
    branch_name: str
    date: str
    records_today: int
    products_sold: int
    confirmed_tomorrow: int
    total_tomorrow: int
    filled_birthdays: int
    total_clients: int


# --- Tasks ---


class UnconfirmedRecord(BaseModel):
    record_id: str
    client_name: str
    service_name: str
    datetime: str
    barber_name: str


class UnfilledBirthday(BaseModel):
    client_id: str
    client_name: str
    phone: str | None
    last_visit: str | None


class UnprocessedCheck(BaseModel):
    record_id: str
    client_name: str
    barber_name: str
    amount: int
    datetime: str
    status: str


class AdminTasksResponse(BaseModel):
    """Tasks overview for a branch."""

    branch_id: str
    date: str
    unconfirmed_records: list[UnconfirmedRecord]
    unfilled_birthdays: list[UnfilledBirthday]
    unprocessed_checks: list[UnprocessedCheck]


class ConfirmRequest(BaseModel):
    """Request body for confirming records."""

    record_ids: list[str]


# --- History ---


class AdminDayResult(BaseModel):
    date: str
    records_count: int
    products_sold: int
    revenue: int
    confirmed_rate: int


class AdminHistoryResponse(BaseModel):
    """Monthly history for a branch."""

    branch_id: str
    month: str
    days: list[AdminDayResult]
