from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class FashionDecision(Base):
    __tablename__ = "fashion_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    action_type: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    observed_units_7d: Mapped[int] = mapped_column(Integer)
    observed_units_30d: Mapped[int] = mapped_column(Integer)
    assumed_stock_on_hand: Mapped[int] = mapped_column(Integer)
    chosen_option: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_units_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_units: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    estimated_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_gross_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_remaining_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feasible: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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


class OlistImport(Base):
    __tablename__ = "olist_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_revision: Mapped[str] = mapped_column(String(80))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    order_count: Mapped[int] = mapped_column(Integer)
    item_count: Mapped[int] = mapped_column(Integer)
    product_count: Mapped[int] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SimulationScenario(Base):
    __tablename__ = "simulation_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    as_of_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stocks: Mapped[list["ScenarioStock"]] = relationship(back_populates="scenario", cascade="all, delete-orphan")


class ScenarioStock(Base):
    __tablename__ = "scenario_stocks"
    __table_args__ = (UniqueConstraint("scenario_id", "product_id", name="uq_scenario_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("simulation_scenarios.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    stock_on_hand: Mapped[int] = mapped_column(Integer)
    inbound_units: Mapped[int] = mapped_column(Integer)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    target_cover_days: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[float] = mapped_column(Float)
    scenario: Mapped[SimulationScenario] = relationship(back_populates="stocks")
    product: Mapped[Product] = relationship()
