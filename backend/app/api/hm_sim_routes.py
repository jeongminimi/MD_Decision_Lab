"""H&M operating simulation: observed sales + synthetic inventory/orders/prices, judged as of a fixed date."""

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (WorkDailySale, WorkDataset, WorkProduct, WorkSimDecision, WorkSimLedger, WorkSimPolicy,
                      WorkSimPrice, WorkSimPurchaseOrder, WorkSimScenario)
from ..services.hm_simulation import import_simulation
from ..services.work_risk import RISK_PRIORITY, classify_work_risk

router = APIRouter(prefix="/api/work/sim", tags=["H&M operating simulation"])
SOURCES = {"sales": "H&M 관측", "conditions": "가상 운영 조건", "results": "시뮬레이션"}
SHORTFALL_NOTE = ("가상 정책상 공급 부족분 = 이후 관측 판매 중 8월 31일의 가상 재고와 계획 입고로 공급할 수 없었던 수량. "
                  "실제 H&M 품절이나 잃은 매출이 아닙니다.")
LIFECYCLE_LABELS = {"fall_new_scenario": "가을 신상 (가상 상태)", "summer_clearance_scenario": "여름 잔여 (가상 상태)",
                    "winter_carryover_scenario": "작년 겨울 행사 (가상 상태)", "unassigned": "상태 미부여"}


def _scenario(scenario_id: int, db: Session) -> WorkSimScenario:
    scenario = db.get(WorkSimScenario, scenario_id)
    if scenario is None:
        raise HTTPException(404, "시뮬레이션을 찾지 못했습니다.")
    return scenario


def _scenario_out(scenario: WorkSimScenario) -> dict:
    return {"id": scenario.id, "dataset_id": scenario.dataset_id, "name": scenario.name,
            "as_of_date": scenario.as_of_date, "ledger_start": scenario.ledger_start,
            "ledger_end": scenario.ledger_end, "source_note": scenario.source_note,
            "bias_note": scenario.bias_note, "shortfall_note": SHORTFALL_NOTE, "sources": SOURCES}


@router.get("/scenarios")
def scenarios(dataset_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(WorkSimScenario).where(WorkSimScenario.dataset_id == dataset_id)
                      .order_by(WorkSimScenario.id)).all()
    return [_scenario_out(row) for row in rows]


@router.post("/import-sample")
def import_sample(dataset_id: int, db: Session = Depends(get_db)):
    """Separate from company uploads: only the bundled, validated simulation can be attached to an H&M dataset."""
    try:
        scenario = import_simulation(db, dataset_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, KeyError, OSError) as exc:
        raise HTTPException(400, f"시뮬레이션 자료를 반영하지 않았습니다: {exc}") from exc
    return _scenario_out(scenario)


def _price_on(prices: list[WorkSimPrice], day: date) -> WorkSimPrice:
    return next(price for price in prices if price.valid_from <= day <= price.valid_to)


def _product_states(scenario: WorkSimScenario, db: Session, only_product: int | None = None) -> list[dict]:
    """Judgment as of the scenario date uses observed sales up to that date only; later days are reported apart."""
    as_of = scenario.as_of_date
    policy_query = select(WorkSimPolicy, WorkProduct).join(WorkProduct, WorkProduct.id == WorkSimPolicy.product_id) \
        .where(WorkSimPolicy.scenario_id == scenario.id)
    if only_product is not None:
        policy_query = policy_query.where(WorkSimPolicy.product_id == only_product)
    pairs = db.execute(policy_query).all()
    ids = [product.id for _, product in pairs]
    daily: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for product_id, day, units in db.execute(
            select(WorkDailySale.product_id, WorkDailySale.sale_date, func.sum(WorkDailySale.units))
            .where(WorkDailySale.product_id.in_(ids), WorkDailySale.sale_date.between(as_of - timedelta(59), as_of))
            .group_by(WorkDailySale.product_id, WorkDailySale.sale_date)):
        daily[product_id][day] = units
    sold_before = set(db.scalars(select(WorkDailySale.product_id).where(
        WorkDailySale.product_id.in_(ids), WorkDailySale.sale_date <= as_of, WorkDailySale.units > 0).distinct()))
    ledgers: dict[int, list[WorkSimLedger]] = defaultdict(list)
    for row in db.scalars(select(WorkSimLedger).where(WorkSimLedger.scenario_id == scenario.id,
                                                       WorkSimLedger.product_id.in_(ids))
                          .order_by(WorkSimLedger.flow_date)):
        ledgers[row.product_id].append(row)
    orders: dict[int, list[WorkSimPurchaseOrder]] = defaultdict(list)
    for row in db.scalars(select(WorkSimPurchaseOrder).where(WorkSimPurchaseOrder.scenario_id == scenario.id,
                                                              WorkSimPurchaseOrder.product_id.in_(ids))):
        orders[row.product_id].append(row)
    prices: dict[int, list[WorkSimPrice]] = defaultdict(list)
    for row in db.scalars(select(WorkSimPrice).where(WorkSimPrice.scenario_id == scenario.id,
                                                      WorkSimPrice.product_id.in_(ids))):
        prices[row.product_id].append(row)

    states = []
    for policy, product in pairs:
        series = daily[product.id]
        units = lambda start, end: sum(v for d, v in series.items() if start <= d <= end)
        u7, u14 = units(as_of - timedelta(6), as_of), units(as_of - timedelta(13), as_of)
        p14, u30 = units(as_of - timedelta(27), as_of - timedelta(14)), units(as_of - timedelta(29), as_of)
        p30 = units(as_of - timedelta(59), as_of - timedelta(30))
        ledger = ledgers[product.id]
        as_of_row = next(row for row in ledger if row.flow_date == as_of)
        stock = as_of_row.closing_stock
        planned = [po for po in orders[product.id] if po.order_date <= as_of and po.expected_receipt_date > as_of]
        planned_30d = sum(po.ordered_units for po in planned if po.expected_receipt_date <= as_of + timedelta(30))
        price = _price_on(prices[product.id], as_of)
        rate = u14 / 14
        cover = round(stock / rate, 1) if rate > 0 else None
        risk, reason, action = classify_work_risk(
            u14=u14, p14=p14, stock=stock, cover=cover, lead_time_days=policy.lead_time_days,
            reorderable=policy.reorderable, observed_any=product.id in sold_before)
        sim_revenue = sim_profit = 0.0
        for row in ledger:
            if as_of - timedelta(29) <= row.flow_date <= as_of:
                segment = _price_on(prices[product.id], row.flow_date)
                sim_revenue += row.supplied_units * segment.selling_price_krw
                sim_profit += row.supplied_units * (segment.selling_price_krw - segment.unit_cost_krw)
        post = [row for row in ledger if row.flow_date > as_of]
        first_short = next((row.flow_date for row in post if row.shortfall_units), None)
        states.append({
            "product_id": product.id, "sku": product.sku, "name": product.name, "section": product.section,
            "category": product.category, "image_ref": product.image_ref,
            "observed": {"units_7d": u7, "units_14d": u14, "prior_14d": p14, "units_30d": u30, "prior_30d": p30,
                         "first_sale_date": policy.observed_first_sale_date, "source": SOURCES["sales"]},
            "conditions": {"stock_on_hand": stock, "planned_inbound_after_as_of": sum(po.ordered_units for po in planned),
                           "planned_inbound_30d": planned_30d, "lead_time_days": policy.lead_time_days,
                           "reorderable": policy.reorderable, "reorder_stop_date": policy.reorder_stop_date,
                           "scenario_lifecycle": policy.scenario_lifecycle,
                           "lifecycle_label": LIFECYCLE_LABELS[policy.scenario_lifecycle],
                           "list_price_krw": price.list_price_krw, "selling_price_krw": price.selling_price_krw,
                           "unit_cost_krw": price.unit_cost_krw, "source": SOURCES["conditions"]},
            "signal": {"risk": risk, "reason": reason, "action": action, "days_of_cover": cover,
                       "simulated_revenue_30d_krw": round(sim_revenue, 2),
                       "simulated_gross_profit_30d_krw": round(sim_profit, 2), "source": SOURCES["results"]},
            "post_as_of": {"start": as_of + timedelta(1), "end": scenario.ledger_end,
                           "observed_units": sum(row.observed_units for row in post),
                           "supplied_units": sum(row.supplied_units for row in post),
                           "policy_shortfall_units": sum(row.shortfall_units for row in post),
                           "first_shortfall_date": first_short,
                           "closing_stock": post[-1].closing_stock if post else stock,
                           "sources": {"observed_units": SOURCES["sales"], "supplied_units": SOURCES["results"],
                                       "policy_shortfall_units": SOURCES["results"]}},
            "_policy": policy, "_ledger": ledger, "_orders": orders[product.id], "_prices": prices[product.id],
        })
    states.sort(key=lambda s: (RISK_PRIORITY[s["signal"]["risk"]], -s["observed"]["units_30d"], s["sku"]))
    return states


def _public(state: dict) -> dict:
    return {key: value for key, value in state.items() if not key.startswith("_")}


@router.get("/analysis")
def analysis(scenario_id: int, db: Session = Depends(get_db)):
    scenario = _scenario(scenario_id, db)
    states = _product_states(scenario, db)
    risks = defaultdict(int)
    for state in states:
        risks[state["signal"]["risk"]] += 1
    post_observed = sum(s["post_as_of"]["observed_units"] for s in states)
    post_short = sum(s["post_as_of"]["policy_shortfall_units"] for s in states)
    return {"scenario": _scenario_out(scenario), "as_of_date": scenario.as_of_date,
            "products": [_public(state) for state in states],
            "summary": {"total_products": len(states), "risk_counts": dict(risks),
                        "attention_count": sum(s["signal"]["risk"] not in {"stable", "not_observed"} for s in states),
                        "units_30d": sum(s["observed"]["units_30d"] for s in states),
                        "simulated_gross_profit_30d_krw": round(sum(s["signal"]["simulated_gross_profit_30d_krw"] for s in states), 2)},
            "post_as_of_summary": {"start": scenario.as_of_date + timedelta(1), "end": scenario.ledger_end,
                                   "observed_units": post_observed, "supplied_units": post_observed - post_short,
                                   "policy_shortfall_units": post_short,
                                   "products_with_shortfall": sum(s["post_as_of"]["policy_shortfall_units"] > 0 for s in states),
                                   "note": SHORTFALL_NOTE}}


def _sim_product(scenario: WorkSimScenario, sku: str, db: Session) -> dict:
    product = db.scalar(select(WorkProduct).where(WorkProduct.dataset_id == scenario.dataset_id, WorkProduct.sku == sku))
    states = _product_states(scenario, db, product.id) if product is not None else []
    if not states:
        raise HTTPException(404, "시뮬레이션 대상 상품이 아닙니다.")
    return states[0]


@router.get("/products/{sku}")
def product_detail(sku: str, scenario_id: int, db: Session = Depends(get_db)):
    scenario = _scenario(scenario_id, db)
    state = _sim_product(scenario, sku, db)
    as_of = scenario.as_of_date
    policy: WorkSimPolicy = state["_policy"]
    return {**_public(state), "scenario": _scenario_out(scenario),
            "policy": {"selection_reason": policy.selection_reason, "assumption_reason": policy.assumption_reason},
            "ledger": [{"date": row.flow_date, "period": "as_of_window" if row.flow_date <= as_of else "post_as_of_observed",
                        "opening_stock": row.opening_stock, "inbound_units": row.inbound_units,
                        "observed_units": row.observed_units, "supplied_units": row.supplied_units,
                        "policy_shortfall_units": row.shortfall_units, "closing_stock": row.closing_stock}
                       for row in state["_ledger"]],
            "planned_orders": [{"po_code": po.po_code, "order_date": po.order_date,
                                "expected_receipt_date": po.expected_receipt_date,
                                "actual_receipt_date": po.actual_receipt_date, "ordered_units": po.ordered_units,
                                "received_units": po.received_units, "status": po.status,
                                "timing": "기준일까지 입고" if po.expected_receipt_date <= as_of else "기준일 이후 입고 예정",
                                "assumption_reason": po.assumption_reason}
                               for po in sorted(state["_orders"], key=lambda po: (po.order_date, po.po_code))],
            "prices": [{"valid_from": p.valid_from, "valid_to": p.valid_to, "list_price_krw": p.list_price_krw,
                        "selling_price_krw": p.selling_price_krw, "unit_cost_krw": p.unit_cost_krw,
                        "price_tier_rule": p.price_tier_rule, "cost_rule": p.cost_rule}
                       for p in sorted(state["_prices"], key=lambda p: p.valid_from)]}


class SimComparePayload(BaseModel):
    scenario_id: int
    sku: str
    discount_pct: float = Field(ge=0, le=70, allow_inf_nan=False)
    expected_units_30d: int = Field(ge=0, le=1_000_000)
    purchase_units: int = Field(default=0, ge=0, le=1_000_000)


def _compare(payload: SimComparePayload, db: Session) -> tuple[dict, dict, WorkSimScenario]:
    scenario = _scenario(payload.scenario_id, db)
    state = _sim_product(scenario, payload.sku, db)
    conditions = state["conditions"]
    if payload.purchase_units and not conditions["reorderable"]:
        raise HTTPException(400, "재발주 불가로 설정된 상품은 추가 매입을 가정할 수 없습니다.")
    purchase_arrival = scenario.as_of_date + timedelta(conditions["lead_time_days"])
    purchase_in_window = conditions["lead_time_days"] <= 30
    available = (conditions["stock_on_hand"] + conditions["planned_inbound_30d"]
                 + (payload.purchase_units if purchase_in_window else 0))
    price = round(conditions["selling_price_krw"] * (1 - payload.discount_pct / 100), 2)
    feasible = payload.expected_units_30d <= available
    result = {
        "sku": payload.sku, "as_of_date": scenario.as_of_date, "discount_pct": payload.discount_pct,
        "expected_units_30d": payload.expected_units_30d, "purchase_units": payload.purchase_units,
        "purchase_arrival_date": purchase_arrival if payload.purchase_units else None,
        "purchase_counted_in_30d": purchase_in_window if payload.purchase_units else None,
        "available_units_30d": available, "proposed_unit_price_krw": price, "unit_cost_krw": conditions["unit_cost_krw"],
        "feasible": feasible,
        "estimated_revenue_krw": round(payload.expected_units_30d * price, 2) if feasible else None,
        "estimated_gross_profit_krw": round(payload.expected_units_30d * (price - conditions["unit_cost_krw"]), 2) if feasible else None,
        "estimated_remaining_units": available - payload.expected_units_30d if feasible else None,
        "source": SOURCES["results"],
        "note": ("가용 수량 = 8월 31일 가상 재고 + 30일 안에 들어오는 계획 입고 + (리드타임이 30일 이내인 경우) 추가 매입. "
                 "예상 판매량은 사용자가 넣은 가정이며, 할인 효과나 실제 H&M 매출이 아닙니다."),
    }
    return result, state, scenario


@router.post("/compare")
def compare(payload: SimComparePayload, db: Session = Depends(get_db)):
    return _compare(payload, db)[0]


class SimDecisionPayload(SimComparePayload):
    action: str = Field(min_length=2, max_length=32)
    rationale: str = Field(min_length=5, max_length=1000)


def _decision_out(decision: WorkSimDecision, sku: str, name: str) -> dict:
    return {"id": decision.id, "sku": sku, "name": name, "as_of_date": decision.as_of_date,
            "action": decision.action, "rationale": decision.rationale, "snapshot": decision.snapshot,
            "created_at": decision.created_at}


@router.post("/decisions")
def save_decision(payload: SimDecisionPayload, db: Session = Depends(get_db)):
    if len(payload.rationale.strip()) < 5:
        raise HTTPException(422, "판단 이유를 다섯 글자 이상 입력하세요.")
    result, state, scenario = _compare(payload, db)
    if not result["feasible"]:
        raise HTTPException(400, "가정 판매량이 30일 가용 수량보다 많습니다. 수량을 수정하세요.")
    snapshot = {"scenario": {"id": scenario.id, "name": scenario.name, "as_of_date": scenario.as_of_date.isoformat()},
                "observed": {**state["observed"], "first_sale_date": _iso(state["observed"]["first_sale_date"])},
                "conditions": {**state["conditions"], "reorder_stop_date": _iso(state["conditions"]["reorder_stop_date"])},
                "signal": state["signal"],
                "comparison": {**result, "as_of_date": scenario.as_of_date.isoformat(),
                               "purchase_arrival_date": _iso(result["purchase_arrival_date"])},
                "bias_note": scenario.bias_note}
    decision = WorkSimDecision(scenario_id=scenario.id, product_id=state["product_id"], as_of_date=scenario.as_of_date,
                               action=payload.action, rationale=payload.rationale.strip(), snapshot=snapshot)
    db.add(decision)
    db.commit()
    return _decision_out(decision, state["sku"], state["name"])


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/decisions")
def decisions(scenario_id: int, db: Session = Depends(get_db)):
    _scenario(scenario_id, db)
    rows = db.execute(select(WorkSimDecision, WorkProduct.sku, WorkProduct.name)
                      .join(WorkProduct, WorkProduct.id == WorkSimDecision.product_id)
                      .where(WorkSimDecision.scenario_id == scenario_id)
                      .order_by(WorkSimDecision.created_at.desc(), WorkSimDecision.id.desc())).all()
    return [_decision_out(decision, sku, name) for decision, sku, name in rows]
