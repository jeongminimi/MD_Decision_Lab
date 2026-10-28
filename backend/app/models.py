from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(80), default="기타")
    stock_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    inbound_units: Mapped[int] = mapped_column(Integer, default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    target_cover_days: Mapped[int] = mapped_column(Integer, default=45)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sales: Mapped[list["DailySale"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    actions: Mapped[list["MDAction"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class MerchandisingContext(Base):
    __tablename__ = "merchandising_contexts"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    season_group: Mapped[str] = mapped_column(String(32))
    lifecycle_status: Mapped[str] = mapped_column(String(32))
    reorderable: Mapped[bool] = mapped_column(default=True)
    launch_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    list_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    planning_note: Mapped[str] = mapped_column(Text, default="")


class DailySale(Base):
    __tablename__ = "daily_sales"
    __table_args__ = (UniqueConstraint("product_id", "sale_date", name="uq_product_sale_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    units_sold: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    product: Mapped[Product] = relationship(back_populates="sales")


class MDAction(Base):
    __tablename__ = "md_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")
    stock_before: Mapped[int] = mapped_column(Integer)
    units_30d_before: Mapped[int] = mapped_column(Integer)
    revenue_30d_before: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    product: Mapped[Product] = relationship(back_populates="actions")


class WorkDataset(Base):
    """An isolated data source for the operational MD workspace."""

    __tablename__ = "work_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # company or hm
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    source_note: Mapped[str] = mapped_column(Text, default="")
    complete_calendar: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkProduct(Base):
    __tablename__ = "work_products"
    __table_args__ = (UniqueConstraint("dataset_id", "sku", name="uq_work_dataset_sku"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("work_datasets.id"), index=True)
    sku: Mapped[str] = mapped_column(String(64))
    product_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(100), default="기타")
    section: Mapped[str] = mapped_column(String(100), default="전체")
    image_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    lifecycle: Mapped[str | None] = mapped_column(String(32), nullable=True)


class WorkDailySale(Base):
    __tablename__ = "work_daily_sales"
    __table_args__ = (UniqueConstraint("product_id", "sale_date", "channel", name="uq_work_product_day_channel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), index=True)
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="전체")
    units: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_profit: Mapped[float | None] = mapped_column(Float, nullable=True)


class WorkProductInput(Base):
    __tablename__ = "work_product_inputs"

    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    stock_on_hand: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inbound_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inbound_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opening_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opening_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_krw: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_cost_krw: Mapped[float | None] = mapped_column(Float, nullable=True)
    reorderable: Mapped[bool | None] = mapped_column(nullable=True)
    source_label: Mapped[str] = mapped_column(String(32))  # company_upload, md_input, simulation


class WorkInputSnapshot(Base):
    __tablename__ = "work_input_snapshots"
    __table_args__ = (UniqueConstraint("product_id", "as_of_date", name="uq_work_input_snapshot_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    stock_on_hand: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inbound_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inbound_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opening_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opening_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_krw: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_cost_krw: Mapped[float | None] = mapped_column(Float, nullable=True)
    reorderable: Mapped[bool | None] = mapped_column(nullable=True)
    source_label: Mapped[str] = mapped_column(String(32))


class WorkDecision(Base):
    __tablename__ = "work_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    action: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    observed_units_14d: Mapped[int] = mapped_column(Integer)
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_units_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assumed_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_gross_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    executed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkSimScenario(Base):
    """A synthetic operating scenario layered on an H&M dataset; observed sales stay in work_daily_sales."""

    __tablename__ = "work_sim_scenarios"
    __table_args__ = (UniqueConstraint("dataset_id", "name", name="uq_work_sim_scenario_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("work_datasets.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    as_of_date: Mapped[date] = mapped_column(Date)
    ledger_start: Mapped[date] = mapped_column(Date)
    ledger_end: Mapped[date] = mapped_column(Date)
    source_note: Mapped[str] = mapped_column(Text)
    bias_note: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkSimPolicy(Base):
    __tablename__ = "work_sim_policies"

    scenario_id: Mapped[int] = mapped_column(ForeignKey("work_sim_scenarios.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), primary_key=True)
    observed_first_sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    scenario_lifecycle: Mapped[str] = mapped_column(String(40))
    reorderable: Mapped[bool] = mapped_column()
    reorder_stop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    selection_reason: Mapped[str] = mapped_column(Text)
    assumption_reason: Mapped[str] = mapped_column(Text)


class WorkSimLedger(Base):
    __tablename__ = "work_sim_ledger"
    __table_args__ = (UniqueConstraint("scenario_id", "product_id", "flow_date", name="uq_work_sim_ledger_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("work_sim_scenarios.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), index=True)
    flow_date: Mapped[date] = mapped_column(Date)
    opening_stock: Mapped[int] = mapped_column(Integer)
    inbound_units: Mapped[int] = mapped_column(Integer)
    observed_units: Mapped[int] = mapped_column(Integer)
    supplied_units: Mapped[int] = mapped_column(Integer)
    shortfall_units: Mapped[int] = mapped_column(Integer)
    closing_stock: Mapped[int] = mapped_column(Integer)


class WorkSimPurchaseOrder(Base):
    __tablename__ = "work_sim_purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("work_sim_scenarios.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), index=True)
    po_code: Mapped[str] = mapped_column(String(32))
    order_date: Mapped[date] = mapped_column(Date)
    expected_receipt_date: Mapped[date] = mapped_column(Date)
    actual_receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ordered_units: Mapped[int] = mapped_column(Integer)
    received_units: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    assumption_reason: Mapped[str] = mapped_column(Text)


class WorkSimPrice(Base):
    __tablename__ = "work_sim_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("work_sim_scenarios.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), index=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    list_price_krw: Mapped[float] = mapped_column(Float)
    selling_price_krw: Mapped[float] = mapped_column(Float)
    unit_cost_krw: Mapped[float] = mapped_column(Float)
    price_tier_rule: Mapped[str] = mapped_column(Text)
    cost_rule: Mapped[str] = mapped_column(Text)


class WorkSimDecision(Base):
    """MD judgment on a simulated product; the snapshot freezes inputs and sources at save time."""

    __tablename__ = "work_sim_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("work_sim_scenarios.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("work_products.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    action: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
