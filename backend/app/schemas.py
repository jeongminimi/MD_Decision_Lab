from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Risk = Literal["out_of_stock", "data_insufficient", "stockout_risk", "overstock_risk", "slow_moving", "healthy"]
ActionType = Literal["replenish", "promotion", "live_exposure", "content_test", "monitor"]


class ProductAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    sku: str
    name: str
    category: str
    season_group: str | None = None
    lifecycle_status: str | None = None
    reorderable: bool | None = None
    launch_date: date | None = None
    event_start_date: date | None = None
    planning_note: str | None = None
    stock_on_hand: int
    inbound_units: int
    lead_time_days: int
    target_cover_days: int
    unit_price: float
    unit_cost: float
    units_7d: int
    units_30d: int
    sales_days_30d: int
    revenue_30d: float
    gross_margin_30d: float
    gross_margin_rate_30d_pct: float | None
    unit_markup_pct: float | None
    margin_is_estimated: bool
    avg_daily_units: float
    avg_daily_7d: float
    decision_daily_units: float
    demand_basis: Literal["7d", "30d", "none"]
    demand_explanation: str
    data_warnings: list[str]
    days_of_cover: float | None
    cover_including_inbound: float | None
    risk: Risk
    risk_label: str
    recommendation: str
    recommendation_reason: str
    suggested_replenishment_units: int | None


class ActionCreate(BaseModel):
    product_id: int
    action_type: ActionType
    note: str = Field(default="", max_length=1000)


class ActionOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    sku: str
    action_type: str
    note: str
    status: str
    stock_before: int
    units_30d_before: int
    revenue_30d_before: float
    created_at: datetime


class SaleImportRow(BaseModel):
    sku: str
    sale_date: date
    units_sold: int = Field(ge=0)
    revenue: float = Field(ge=0)
    gross_margin: float | None = None


class SaleImportResult(BaseModel):
    imported: int
    rejected: int
    messages: list[str]


