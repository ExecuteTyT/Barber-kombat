"""Pydantic schemas for Report API endpoints."""

import uuid

from pydantic import BaseModel, ConfigDict

# --- Daily revenue report ---


class BranchRevenue(BaseModel):
    """Revenue data for a single branch."""

    branch_id: str
    name: str
    revenue_today: int
    revenue_mtd: int
    plan_target: int
    plan_percentage: float
    barbers_in_shift: int
    barbers_total: int


class DailyRevenueReport(BaseModel):
    """Daily revenue report across all branches."""

    date: str
    branches: list[BranchRevenue]
    network_total_today: int
    network_total_mtd: int


# --- Day-to-day comparison ---


class DailyDataPoint(BaseModel):
    """Single day in a cumulative revenue series."""

    day: int
    amount: int


class MonthCumulative(BaseModel):
    """Cumulative revenue data for a month."""

    name: str
    daily_cumulative: list[DailyDataPoint]


class Comparison(BaseModel):
    """Percentage changes vs previous months."""

    vs_prev: str
    vs_prev_prev: str


class DayToDayReport(BaseModel):
    """Day-to-day month comparison report."""

    branch_id: str | None
    period_end: str
    current_month: MonthCumulative
    prev_month: MonthCumulative
    prev_prev_month: MonthCumulative
    comparison: Comparison


# --- Clients report ---


class BranchClients(BaseModel):
    """Client statistics for a single branch."""

    branch_id: str
    name: str
    new_clients_today: int
    returning_clients_today: int
    total_today: int
    new_clients_mtd: int
    returning_clients_mtd: int
    total_mtd: int


class ClientsReport(BaseModel):
    """Client statistics report."""

    date: str
    branches: list[BranchClients]
    network_new_mtd: int
    network_returning_mtd: int
    network_total_mtd: int


# --- Kombat daily standings ---


class BarberStanding(BaseModel):
    """Single barber standing in daily Kombat."""

    barber_id: str
    name: str
    rank: int
    total_score: float
    revenue: int
    revenue_score: float
    cs_value: float
    cs_score: float
    products_count: int
    products_score: float
    extras_count: int
    extras_score: float
    reviews_avg: float | None
    reviews_score: float


class BranchStanding(BaseModel):
    """Kombat standings for a branch."""

    branch_id: str
    name: str
    standings: list[BarberStanding]


class KombatDailyReport(BaseModel):
    """Daily Kombat standings report."""

    date: str
    branches: list[BranchStanding]


# --- Kombat monthly summary ---


class BarberMonthlySummary(BaseModel):
    """Single barber monthly Kombat summary."""

    barber_id: str
    name: str
    days_worked: int
    total_revenue: int
    avg_score: float
    wins: int
    rank: int


class BranchMonthlySummary(BaseModel):
    """Monthly Kombat summary for a branch."""

    branch_id: str
    name: str
    standings: list[BarberMonthlySummary]


class KombatMonthlyReport(BaseModel):
    """Monthly Kombat summary report."""

    month: str
    branches: list[BranchMonthlySummary]


# --- Generic report response ---


class ReportResponse(BaseModel):
    """Generic response wrapping a report's data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    date: str
    branch_id: uuid.UUID | None
    data: dict
    delivered_telegram: bool


class ReportListResponse(BaseModel):
    """List of reports."""

    reports: list[ReportResponse]
