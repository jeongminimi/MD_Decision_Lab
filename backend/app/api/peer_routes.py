"""Observed peer sales and MD season plans; synthetic stock is never peer sales."""

from datetime import date, timedelta
from math import ceil
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (WorkCatalogProduct, WorkCatalogSalesSnapshot, WorkCatalogWeekSale,
                      WorkDataset, WorkProduct, WorkSeasonPlan, WorkSimLedger,
                      WorkSimPolicy, WorkSimPurchaseOrder, WorkSimScenario)

router = APIRouter(prefix="/api/work", tags=["MD peer comparison"])
AS_OF = date(2020, 8, 31)


def _snapshot(dataset_id: int, sku: str, db: Session) -> WorkCatalogSalesSnapshot:
    row = db.scalar(select(WorkCatalogSalesSnapshot).where(
        WorkCatalogSalesSnapshot.dataset_id == dataset_id,
        WorkCatalogSalesSnapshot.as_of_date == AS_OF,
        WorkCatalogSalesSnapshot.sku == sku))
    if row is None:
        raise HTTPException(404, "8월 31일 기준 전체 상품 판매 집계가 없습니다.")
    return row


def _cohort(dataset_id: int, section: str, category: str, scope: str, db: Session):
    return db.scalars(select(WorkCatalogSalesSnapshot).where(
        WorkCatalogSalesSnapshot.dataset_id == dataset_id,
        WorkCatalogSalesSnapshot.as_of_date == AS_OF,
        WorkCatalogSalesSnapshot.section == section,
        WorkCatalogSalesSnapshot.category == category,
        WorkCatalogSalesSnapshot.scope == scope)).all()


def _peer_numbers(row: WorkCatalogSalesSnapshot, cohort: list[WorkCatalogSalesSnapshot]) -> dict:
    active14 = [item.units_14d for item in cohort if item.units_14d > 0]
    active7 = [item.units_7d for item in cohort if item.units_7d > 0]

    def rank(value: int, numbers: list[int]):
        return 1 + sum(other > value for other in numbers) if value > 0 and numbers else None

    return {"registered": len(cohort), "active_14d": len(active14), "active_7d": len(active7),
            "rank_14d": rank(row.units_14d, active14), "rank_7d": rank(row.units_7d, active7),
            "median_14d": median(active14) if active14 else None,
            "median_7d": median(active7) if active7 else None,
            "enough_peers": len(active14) >= 20}


def _inventory_context(dataset_id: int, sku: str, db: Session) -> dict | None:
    scenario = db.scalar(select(WorkSimScenario).where(WorkSimScenario.dataset_id == dataset_id,
                                                       WorkSimScenario.as_of_date == AS_OF)
                         .order_by(WorkSimScenario.id.desc()))
    product = db.scalar(select(WorkProduct).where(WorkProduct.dataset_id == dataset_id, WorkProduct.sku == sku))
    if scenario is None or product is None:
        return None
    policy = db.get(WorkSimPolicy, (scenario.id, product.id))
    ledger = db.scalar(select(WorkSimLedger).where(WorkSimLedger.scenario_id == scenario.id,
                                                  WorkSimLedger.product_id == product.id,
                                                  WorkSimLedger.flow_date == AS_OF))
    if policy is None or ledger is None:
        return None
    orders = db.scalars(select(WorkSimPurchaseOrder).where(
        WorkSimPurchaseOrder.scenario_id == scenario.id,
        WorkSimPurchaseOrder.product_id == product.id,
        WorkSimPurchaseOrder.order_date <= AS_OF,
        WorkSimPurchaseOrder.expected_receipt_date > AS_OF)).all()
    return {"stock_on_hand": ledger.closing_stock, "lead_time_days": policy.lead_time_days,
            "reorderable": policy.reorderable,
            "inbound_before_lead": sum(po.ordered_units for po in orders
                                       if po.expected_receipt_date <= AS_OF + timedelta(days=policy.lead_time_days)),
            "source": "가상 운영 조건"}


@router.get("/peers/{sku}")
def peers(sku: str, dataset_id: int, db: Session = Depends(get_db)):
    row = _snapshot(dataset_id, sku, db)
    if row.scope == "other":
        return {"sku": sku, "scope": "other", "as_of_date": AS_OF,
                "note": "의류·액세서리 외 상품은 이번 동종 비교 범위에 포함하지 않았습니다."}
    cohort = _cohort(dataset_id, row.section, row.category, row.scope, db)
    names = {item.sku: item.name for item in db.scalars(select(WorkCatalogProduct).where(
        WorkCatalogProduct.dataset_id == dataset_id,
        WorkCatalogProduct.sku.in_([item.sku for item in cohort]))).all()}
    numbers = _peer_numbers(row, cohort)
    inventory = _inventory_context(dataset_id, sku, db)
    replenishment = None
    if inventory is not None:
        daily = row.units_14d / 14
        lead = inventory["lead_time_days"]
        safety_days = 7
        target = ceil(daily * (lead + safety_days))
        proposal = max(0, target - inventory["stock_on_hand"] - inventory["inbound_before_lead"])
        replenishment = {"daily_units": round(daily, 2), "safety_days": safety_days,
                         "target_units": target, "review_units": proposal if inventory["reorderable"] else None,
                         "cover_days": round(inventory["stock_on_hand"] / daily, 1) if daily else None,
                         "note": "최근 14일 일평균 × (입고 소요일 + 안전 7일) − 현재고 − 기한 내 계획 입고. 발주 확정량이 아닌 검토 기준입니다."}
    top = sorted(cohort, key=lambda item: (-item.units_14d, item.sku))[:6]
    return {"sku": sku, "scope": row.scope, "as_of_date": AS_OF,
            "section": row.section, "category": row.category,
            "observed": {"units_7d": row.units_7d, "prior_7d": row.prior_7d,
                         "units_14d": row.units_14d, "prior_14d": row.prior_14d},
            "comparison": numbers,
            "top_peers": [{"sku": item.sku, "name": names.get(item.sku, item.sku),
                           "units_14d": item.units_14d} for item in top],
            "inventory": inventory, "replenishment": replenishment,
            "note": "판매 순위는 H&M 관측 수량 기준입니다. 판매 가능 기간·노출량·실제 재고는 확인되지 않습니다."}


@router.get("/season-groups")
def season_groups(dataset_id: int, db: Session = Depends(get_db)):
    rows = db.execute(select(WorkCatalogSalesSnapshot.section, WorkCatalogSalesSnapshot.category,
                             WorkCatalogSalesSnapshot.scope, func.count(),
                             func.sum(WorkCatalogSalesSnapshot.units_14d))
                      .where(WorkCatalogSalesSnapshot.dataset_id == dataset_id,
                             WorkCatalogSalesSnapshot.as_of_date == AS_OF,
                             WorkCatalogSalesSnapshot.scope.in_(("apparel", "accessory")))
                      .group_by(WorkCatalogSalesSnapshot.section, WorkCatalogSalesSnapshot.category,
                                WorkCatalogSalesSnapshot.scope)
                      .order_by(func.sum(WorkCatalogSalesSnapshot.units_14d).desc())).all()
    return [{"section": section, "category": category, "scope": scope,
             "products": count, "units_14d": units or 0} for section, category, scope, count, units in rows]


def _season_review(dataset_id: int, section: str, category: str, scope: str, db: Session) -> dict:
    if scope not in {"apparel", "accessory"}:
        raise HTTPException(400, "의류 또는 액세서리 범위를 선택해 주세요.")
    cohort = _cohort(dataset_id, section, category, scope, db)
    if not cohort:
        raise HTTPException(404, "해당 의류·액세서리 상품군이 없습니다.")
    skus = [item.sku for item in cohort]
    weeks = db.scalars(select(WorkCatalogWeekSale).where(
        WorkCatalogWeekSale.dataset_id == dataset_id,
        WorkCatalogWeekSale.sku.in_(skus),
        WorkCatalogWeekSale.year.in_((2019, 2020)))).all()
    series = {2019: [0] * 9, 2020: [0] * 9}
    by_sku: dict[str, dict[int, int]] = {}
    for item in weeks:
        series[item.year][item.week_index] += item.units
        by_sku.setdefault(item.sku, {2019: 0, 2020: 0})[item.year] += item.units
    names = {item.sku: item.name for item in db.scalars(select(WorkCatalogProduct).where(
        WorkCatalogProduct.dataset_id == dataset_id, WorkCatalogProduct.sku.in_(skus))).all()}
    current_order = sorted(cohort, key=lambda item: (-by_sku.get(item.sku, {}).get(2020, 0), item.sku))
    previous_order = sorted(cohort, key=lambda item: (-by_sku.get(item.sku, {}).get(2019, 0), item.sku))
    # Show strong products from both years, including former bests that faded this year.
    selected = {item.sku for item in current_order[:6]} | {item.sku for item in previous_order[:6]}
    for item in current_order:
        if len(selected) >= 12:
            break
        selected.add(item.sku)
    candidates = [item for item in current_order if item.sku in selected]
    return {"as_of_date": AS_OF, "section": section, "category": category,
            "scope": cohort[0].scope, "registered": len(cohort),
            "weekly": [{"week_index": i, "start_2019": (date(2019, 7, 1) + timedelta(days=7*i)).isoformat(),
                        "start_2020": (date(2020, 7, 1) + timedelta(days=7*i)).isoformat(),
                        "units_2019": series[2019][i], "units_2020": series[2020][i]}
                       for i in range(9)],
            "totals": {"2019": sum(series[2019]), "2020": sum(series[2020]),
                       "active_2019": sum(v[2019] > 0 for v in by_sku.values()),
                       "active_2020": sum(v[2020] > 0 for v in by_sku.values())},
            "candidates": [{"sku": item.sku, "name": names.get(item.sku, item.sku),
                            "units_2019": by_sku.get(item.sku, {}).get(2019, 0),
                            "units_2020": by_sku.get(item.sku, {}).get(2020, 0),
                            "units_14d": item.units_14d} for item in candidates],
            "note": "2019·2020년 7/1~8/31의 같은 주차 관측 판매입니다. 상품 수·노출·할인·재고 차이는 보정하지 않았습니다."}


@router.get("/season-review")
def season_review(dataset_id: int, section: str = Query(..., max_length=100),
                  category: str = Query(..., max_length=100), scope: str = Query(...), db: Session = Depends(get_db)):
    return _season_review(dataset_id, section, category, scope, db)


class PlanCandidate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    planned_units: int = Field(ge=1, le=1_000_000)


class SeasonPlanInput(BaseModel):
    dataset_id: int
    scope: str = Field(pattern="^(apparel|accessory)$")
    section: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=100)
    candidates: list[PlanCandidate] = Field(min_length=2, max_length=5)
    rationale: str = Field(min_length=5, max_length=2000)


@router.post("/season-plans")
def save_season_plan(payload: SeasonPlanInput, db: Session = Depends(get_db)):
    dataset = db.get(WorkDataset, payload.dataset_id)
    if dataset is None or dataset.kind != "hm":
        raise HTTPException(400, "H&M 시연 작업공간에서만 이 판매 비교를 저장합니다.")
    review = _season_review(payload.dataset_id, payload.section, payload.category, payload.scope, db)
    selected = [item.sku for item in payload.candidates]
    if len(set(selected)) != len(selected):
        raise HTTPException(400, "같은 상품을 중복 선택할 수 없습니다.")
    allowed = {item["sku"] for item in review["candidates"]}
    if not set(selected) <= allowed:
        raise HTTPException(400, "현재 비교 상품군의 기획 후보만 선택할 수 있습니다.")
    if len(payload.rationale.strip()) < 5:
        raise HTTPException(400, "판단 이유를 5자 이상 입력해 주세요.")
    plan = WorkSeasonPlan(dataset_id=payload.dataset_id, as_of_date=AS_OF,
                          section=payload.section, category=payload.category,
                          candidate_skus=[item.model_dump() for item in payload.candidates],
                          planned_units=sum(item.planned_units for item in payload.candidates),
                          rationale=payload.rationale.strip(), sales_snapshot=jsonable_encoder(review))
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"id": plan.id, "created_at": plan.created_at, "planned_units": plan.planned_units}


@router.get("/season-plans")
def season_plans(dataset_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(WorkSeasonPlan).where(WorkSeasonPlan.dataset_id == dataset_id)
                      .order_by(WorkSeasonPlan.id.desc())).all()
    return [{"id": row.id, "section": row.section, "category": row.category,
             "as_of_date": row.as_of_date, "candidates": row.candidate_skus,
             "planned_units": row.planned_units, "rationale": row.rationale,
             "created_at": row.created_at, "sales_snapshot": row.sales_snapshot} for row in rows]
