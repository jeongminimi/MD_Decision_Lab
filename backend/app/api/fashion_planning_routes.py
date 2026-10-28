"""Reconciled synthetic stock history and prior-season planning examples."""

import csv
from datetime import date
from math import ceil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailySale, FashionPriorReference, FashionSeasonPlanDecision, FashionStockFlow, Product

router = APIRouter(prefix="/api/fashion/planning", tags=["Synthetic fashion planning"])
CASE_DIR = Path(__file__).resolve().parents[3] / "sample_data" / "fashion_fw_case"
SNAPSHOT_DATE = date(2026, 8, 31)


class PlanDecisionInput(BaseModel):
    sku: str
    growth_pct: float = Field(ge=-30, le=50, allow_inf_nan=False)
    target_sell_through_pct: float = Field(ge=60, le=95, allow_inf_nan=False)
    rationale: str = Field(min_length=5, max_length=1000)


def _rows(filename: str) -> list[dict[str, str]]:
    with (CASE_DIR / filename).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


@router.get("/status")
def planning_status(db: Session = Depends(get_db)):
    flows = db.scalar(select(func.count(FashionStockFlow.id))) or 0
    references = db.scalar(select(func.count(FashionPriorReference.product_id))) or 0
    return {"ready": flows == 1800 and references == 12,
            "flow_rows": flows, "reference_rows": references,
            "source": "재현 가능한 합성 운영자료; 실제 회사 실적 아님"}


@router.post("/import-sample")
def import_planning_sample(db: Session = Depends(get_db)):
    """Add separate ledger tables once, preserving all current product and sale rows."""
    if (db.scalar(select(func.count(FashionStockFlow.id))) or 0) or (db.scalar(select(func.count(FashionPriorReference.product_id))) or 0):
        raise HTTPException(status_code=409, detail="운영 자료가 이미 있습니다. 기존 기록을 덮어쓰지 않았습니다.")
    products = {p.sku: p for p in db.scalars(select(Product).where(Product.sku.like("FSH-%")))}
    if len(products) != 30:
        raise HTTPException(status_code=409, detail="의류 사례를 먼저 연결하세요.")
    try:
        flow_rows = _rows("fashion_stock_flow_2026.csv")
        reference_rows = _rows("fashion_prior_fw_reference.csv")
        source_products = {r["sku"]: r for r in _rows("fashion_products_realistic_v2.csv")}
        source_sales = {(r["sku"], r["sale_date"]): int(r["units_sold"])
                        for r in _rows("fashion_daily_sales_realistic_v2.csv")}
        if len(flow_rows) != 1800 or len(reference_rows) != 12 or len(source_sales) != 1800:
            raise ValueError("원본 파일의 행 수를 확인하세요.")
        last: dict[str, tuple[date, int]] = {}
        seen = set()
        for row in flow_rows:
            sku, day = row["sku"], date.fromisoformat(row["date"])
            key = (sku, day)
            if sku not in products or key in seen:
                raise ValueError(f"SKU 또는 날짜 중복: {key}")
            seen.add(key)
            numbers = {k: int(row[k]) for k in ("opening_stock", "receipts", "customer_returns",
                       "supplier_returns", "writeoffs", "adjustments", "sold_units", "closing_stock")}
            if any(numbers[k] < 0 for k in numbers if k != "adjustments"):
                raise ValueError(f"음수 재고 수불: {key}")
            expected = (numbers["opening_stock"] + numbers["receipts"] + numbers["customer_returns"]
                        - numbers["supplier_returns"] - numbers["writeoffs"] + numbers["adjustments"]
                        - numbers["sold_units"])
            if expected != numbers["closing_stock"] or source_sales.get((sku, day.isoformat())) != numbers["sold_units"]:
                raise ValueError(f"판매·재고 수불 불일치: {key}")
            if sku in last and (day <= last[sku][0] or numbers["opening_stock"] != last[sku][1]):
                raise ValueError(f"일별 재고 연결 불일치: {key}")
            last[sku] = (day, numbers["closing_stock"])
            db.add(FashionStockFlow(product_id=products[sku].id, flow_date=day, **numbers))
        if len(seen) != 1800 or any(last[sku] != (SNAPSHOT_DATE, int(row["stock_on_hand"]))
                                     for sku, row in source_products.items()):
            raise ValueError("기준일 마감 재고와 상품 마스터가 다릅니다.")
        seen_refs = set()
        for row in reference_rows:
            sku = row["current_sku"]
            if sku not in products or not sku.startswith("FSH-FW-") or sku in seen_refs:
                raise ValueError(f"비교 상품 연결 오류: {sku}")
            seen_refs.add(sku)
            numbers = {k: int(row[k]) for k in ("first_order", "later_receipts", "customer_returns",
                       "supplier_returns", "writeoffs", "sold_units", "end_stock", "sales_revenue", "gross_profit")}
            if any(v < 0 for v in numbers.values()):
                raise ValueError(f"비교 상품 음수 값: {sku}")
            if (numbers["first_order"] + numbers["later_receipts"] + numbers["customer_returns"]
                - numbers["supplier_returns"] - numbers["writeoffs"] - numbers["sold_units"] != numbers["end_stock"]):
                raise ValueError(f"비교 상품 재고 수불 불일치: {sku}")
            db.add(FashionPriorReference(product_id=products[sku].id,
                   reference_name=row["reference_name"], season=row["season"], **numbers))
        db.commit()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"운영 자료 검증 실패: {exc}") from exc
    return {"ready": True, "flow_rows": 1800, "reference_rows": 12}


@router.get("/analysis")
def planning_analysis(growth_pct: float = Query(default=0, ge=-30, le=50),
                      target_sell_through_pct: float = Query(default=85, ge=60, le=95),
                      db: Session = Depends(get_db)):
    if (db.scalar(select(func.count(FashionStockFlow.id))) or 0) != 1800:
        raise HTTPException(status_code=409, detail="운영 자료를 먼저 연결하세요.")
    products = {p.id: p for p in db.scalars(select(Product).where(Product.sku.like("FSH-%")))}
    all_flows = db.scalars(select(FashionStockFlow).order_by(FashionStockFlow.product_id, FashionStockFlow.flow_date)).all()
    by_product: dict[int, list[FashionStockFlow]] = {}
    for flow in all_flows:
        by_product.setdefault(flow.product_id, []).append(flow)
    source_sales: dict[int, list[DailySale]] = {}
    for sale in db.scalars(select(DailySale).where(DailySale.product_id.in_(products))):
        source_sales.setdefault(sale.product_id, []).append(sale)
    flow_summary = []
    for product_id, flows in by_product.items():
        product = products[product_id]
        receipts = sum(f.receipts for f in flows)
        returned = sum(f.customer_returns for f in flows)
        removed = sum(f.supplier_returns + f.writeoffs for f in flows)
        sold = sum(f.sold_units for f in flows)
        available = flows[0].opening_stock + receipts + returned - removed + sum(f.adjustments for f in flows)
        current_sales = sum(s.units_sold for s in source_sales.get(product_id, [])
                            if flows[0].flow_date <= s.sale_date <= SNAPSHOT_DATE)
        flow_summary.append({"sku": product.sku, "name": product.name, "season_group": product.sku[4:6],
                             "opening_stock": flows[0].opening_stock, "receipts": receipts,
                             "customer_returns": returned, "removed_units": removed,
                             "sold_units": sold, "closing_stock": flows[-1].closing_stock,
                             "sell_through_pct": round(sold / available * 100, 1) if available > 0 else None,
                             "reconciled_with_current_inputs": current_sales == sold and product.stock_on_hand == flows[-1].closing_stock,
                             "note": "출시 전 미판매" if product.sku.startswith("FSH-FW-") else "합성 운영 수불"})
    plans = []
    for ref in db.scalars(select(FashionPriorReference).order_by(FashionPriorReference.product_id)):
        product = products[ref.product_id]
        prior_available = ref.first_order + ref.later_receipts + ref.customer_returns - ref.supplier_returns - ref.writeoffs
        demand = ceil(ref.sold_units * (1 + growth_pct / 100))
        target_supply = ceil(demand / (target_sell_through_pct / 100))
        current_supply = product.stock_on_hand + product.inbound_units
        additional_order = max(target_supply - current_supply, 0)
        excess = max(current_supply - target_supply, 0)
        inbound_reduction = min(excess, product.inbound_units)
        planned_supply = current_supply + additional_order
        saleable = min(demand, planned_supply)
        unit_margin = product.unit_price - product.unit_cost
        plans.append({"sku": product.sku, "name": product.name, "reference_name": ref.reference_name,
                      "prior_available_units": prior_available, "prior_sold_units": ref.sold_units,
                      "prior_end_stock": ref.end_stock, "prior_revenue": ref.sales_revenue,
                      "prior_gross_profit": ref.gross_profit,
                      "prior_sell_through_pct": round(ref.sold_units / prior_available * 100, 1),
                      "current_stock": product.stock_on_hand, "inbound_units": product.inbound_units,
                      "current_supply": current_supply, "assumed_demand": demand,
                      "target_supply": target_supply, "additional_order_to_review": additional_order,
                      "excess_units_to_review": excess,
                      "inbound_reduction_to_review": inbound_reduction,
                      "recommended_action": "추가 발주 조건 검토" if additional_order else (
                          "입고 예정 조정·노출 검토" if excess else "현 물량 유지"),
                      "planned_supply": planned_supply, "projected_sales": saleable,
                      "projected_end_stock": planned_supply - saleable,
                      "projected_revenue": round(saleable * product.unit_price, 2),
                      "projected_gross_profit": round(saleable * unit_margin, 2),
                      "note": "작년 비교 상품을 기준으로 한 가정; 실제 수요 예측이나 확정 발주량이 아닙니다."})
    plans.sort(key=lambda item: (item["additional_order_to_review"], item["excess_units_to_review"]), reverse=True)
    return {"source": "전체가 합성 사례 데이터", "as_of_date": SNAPSHOT_DATE,
            "growth_pct": growth_pct, "target_sell_through_pct": target_sell_through_pct,
            "flow_summary": flow_summary, "plans": plans,
            "warning": "현재 상품·판매 값을 수정한 경우 수불표와 일치하지 않을 수 있습니다. 불일치 상품은 판매율을 현재 실적으로 해석하지 마세요. 입고 예정은 실제 입고가 아닙니다."}


@router.get("/decisions")
def list_plan_decisions(db: Session = Depends(get_db)):
    rows = db.execute(select(FashionSeasonPlanDecision, Product.sku, Product.name)
                      .join(Product, FashionSeasonPlanDecision.product_id == Product.id)
                      .order_by(FashionSeasonPlanDecision.id.desc()).limit(30)).all()
    return [{"id": record.id, "sku": sku, "name": name, "growth_pct": record.growth_pct,
             "target_sell_through_pct": record.target_sell_through_pct,
             "prior_sold_units": record.prior_sold_units, "current_supply": record.current_supply,
             "assumed_demand": record.assumed_demand, "target_supply": record.target_supply,
             "additional_order_to_review": record.additional_order_to_review,
             "excess_units_to_review": record.excess_units_to_review,
             "rationale": record.rationale, "created_at": record.created_at}
            for record, sku, name in rows]


@router.post("/decisions")
def save_plan_decision(payload: PlanDecisionInput, db: Session = Depends(get_db)):
    if len(payload.rationale.strip()) < 5:
        raise HTTPException(status_code=422, detail="판단 이유를 다섯 글자 이상 입력하세요.")
    calculated = planning_analysis(payload.growth_pct, payload.target_sell_through_pct, db)
    plan = next((p for p in calculated["plans"] if p["sku"] == payload.sku), None)
    if plan is None:
        raise HTTPException(status_code=404, detail="가을 신상 비교 상품을 찾지 못했습니다.")
    product = db.scalar(select(Product).where(Product.sku == payload.sku))
    record = FashionSeasonPlanDecision(
        product_id=product.id, growth_pct=payload.growth_pct,
        target_sell_through_pct=payload.target_sell_through_pct,
        prior_sold_units=plan["prior_sold_units"], current_supply=plan["current_supply"],
        assumed_demand=plan["assumed_demand"], target_supply=plan["target_supply"],
        additional_order_to_review=plan["additional_order_to_review"],
        excess_units_to_review=plan["excess_units_to_review"], rationale=payload.rationale.strip())
    db.add(record)
    db.commit()
    return {"id": record.id, "sku": payload.sku, "saved": True,
            "note": "기획 검토 기록만 저장했습니다. 재고·발주·판매 데이터는 변경하지 않았습니다."}
