"""User-owned execution records, distinct from imported H&M operating assumptions."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (WorkDataset, WorkDecision, WorkOperation, WorkOperationEvent,
                      WorkProduct, WorkSimDecision, WorkInputSnapshot)

router = APIRouter(prefix="/api/work/operations", tags=["execution records"])


class CreateOperation(BaseModel):
    decision_source: str
    decision_id: int
    planned_start: date
    planned_end: date | None = None
    planned_units: int | None = Field(default=None, ge=1)
    expected_receipt_date: date | None = None
    note: str = Field(default="", max_length=1000)


class AddEvent(BaseModel):
    event_date: date
    kind: str
    units: int | None = Field(default=None, ge=0)
    revenue_krw: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    note: str = Field(default="", max_length=1000)
    client_key: str | None = Field(default=None, max_length=64)


def _kind(action: str) -> str:
    if "매입" in action:
        return "replenish"
    if "기획전" in action:
        return "campaign"
    if "할인" in action:
        return "discount"
    raise HTTPException(400, "발주·할인·기획전 판단에서만 실행 계획을 만들 수 있습니다.")


def _out(op: WorkOperation, db: Session) -> dict:
    events = db.scalars(select(WorkOperationEvent).where(WorkOperationEvent.operation_id == op.id)
                        .order_by(WorkOperationEvent.event_date, WorkOperationEvent.id)).all()
    # One product has one continuing inventory timeline across its plans.
    product_ops = db.scalars(select(WorkOperation).where(WorkOperation.product_id == op.product_id)
                             .order_by(WorkOperation.id)).all()
    stock = product_ops[0].opening_stock if product_ops else op.opening_stock
    balances: dict[int, int | None] = {}
    all_events = db.scalars(select(WorkOperationEvent).where(
        WorkOperationEvent.operation_id.in_([row.id for row in product_ops]))
        .order_by(WorkOperationEvent.event_date, WorkOperationEvent.id)).all()
    for event in all_events:
        if event.kind == "received" and stock is not None:
            stock += event.units or 0
        elif event.kind == "sale" and stock is not None:
            stock -= event.units or 0
        elif event.kind == "stock_count":
            stock = event.units
        balances[event.id] = stock
    received = sold = 0
    sale_events = []
    for event in events:
        if event.kind == "received":
            received += event.units or 0
        elif event.kind == "sale":
            sold += event.units or 0
            sale_events.append(event)
    actual_revenue = (round(sum(e.revenue_krw for e in sale_events), 2)
                      if sale_events and all(e.revenue_krw is not None for e in sale_events) else None)
    actual_profit = (round(actual_revenue - sold * op.unit_cost_krw, 2)
                     if actual_revenue is not None and op.unit_cost_krw is not None else None)
    period_days = (op.planned_end - op.planned_start).days + 1 if op.planned_end else None
    expected_period_units = (round(op.expected_sales_units * period_days / 30)
                             if period_days is not None and op.expected_sales_units is not None else None)
    expected_period_revenue = (round(op.expected_revenue_krw * period_days / 30, 2)
                               if period_days is not None and op.expected_revenue_krw is not None else None)
    expected_period_profit = (round(op.expected_profit_krw * period_days / 30, 2)
                              if period_days is not None and op.expected_profit_krw is not None else None)
    product = db.get(WorkProduct, op.product_id)
    return {"id": op.id, "dataset_id": op.dataset_id, "sku": product.sku, "name": product.name,
            "kind": op.kind, "status": op.status, "source_label": op.source_label,
            "planned_start": op.planned_start, "planned_end": op.planned_end,
            "planned_units": op.planned_units, "expected_receipt_date": op.expected_receipt_date,
            "opening_stock": op.opening_stock, "current_stock": stock,
            "expected_sales_units": op.expected_sales_units, "expected_revenue_krw": op.expected_revenue_krw,
            "expected_profit_krw": op.expected_profit_krw, "discount_pct": op.discount_pct,
            "period_days": period_days, "expected_period_units": expected_period_units,
            "expected_period_revenue_krw": expected_period_revenue,
            "expected_period_profit_krw": expected_period_profit,
            "received_units": received, "recorded_sales_units": sold,
            "recorded_revenue_krw": actual_revenue, "recorded_profit_krw": actual_profit,
            "note": op.note, "events": [{"id": e.id, "event_date": e.event_date, "kind": e.kind,
            "units": e.units, "revenue_krw": e.revenue_krw, "stock_after": balances.get(e.id),
            "note": e.note} for e in events]}


@router.post("")
def create_operation(payload: CreateOperation, db: Session = Depends(get_db)):
    if payload.decision_source == "sim":
        decision = db.get(WorkSimDecision, payload.decision_id)
        if decision is None:
            raise HTTPException(404, "판단 기록을 찾지 못했습니다.")
        comparison = decision.snapshot["comparison"]
        dataset_id = db.get(WorkProduct, decision.product_id).dataset_id
        link = {"sim_decision_id": decision.id}
        stock = comparison.get("stock_on_hand")
        cost = comparison.get("unit_cost_krw")
    elif payload.decision_source == "work":
        decision = db.get(WorkDecision, payload.decision_id)
        if decision is None:
            raise HTTPException(404, "판단 기록을 찾지 못했습니다.")
        dataset_id = db.get(WorkProduct, decision.product_id).dataset_id
        selected = (decision.comparison_snapshot or {}).get("selected_option", "B")
        comparison = (decision.comparison_snapshot or {}).get(selected, {})
        link = {"work_decision_id": decision.id}
        inputs = db.scalar(select(WorkInputSnapshot).where(
            WorkInputSnapshot.product_id == decision.product_id,
            WorkInputSnapshot.as_of_date == decision.as_of_date))
        stock = inputs.stock_on_hand if inputs else None
        cost = inputs.unit_cost_krw if inputs else None
    else:
        raise HTTPException(400, "판단 기록의 출처가 올바르지 않습니다.")
    kind = _kind(decision.action)
    if payload.planned_start < decision.as_of_date:
        raise HTTPException(400, "계획 시작일은 판단 기준일보다 빠를 수 없습니다.")
    if kind == "replenish":
        units = payload.planned_units or comparison.get("purchase_units")
        arrival = payload.expected_receipt_date or comparison.get("purchase_arrival_date")
        if not units or not arrival:
            raise HTTPException(400, "발주 수량과 예상 입고일을 입력하세요.")
        if isinstance(arrival, str):
            arrival = date.fromisoformat(arrival)
        if arrival < payload.planned_start:
            raise HTTPException(400, "예상 입고일은 발주일보다 빠를 수 없습니다.")
    else:
        units = arrival = None
        if payload.planned_end is None or not payload.planned_start <= payload.planned_end <= payload.planned_start + timedelta(days=29):
            raise HTTPException(400, "행사 기간은 시작일을 포함해 1~30일로 입력하세요.")
    existing = db.scalar(select(WorkOperation).where(
        WorkOperation.sim_decision_id == decision.id if payload.decision_source == "sim"
        else WorkOperation.work_decision_id == decision.id))
    if existing:
        raise HTTPException(409, "이 판단에 연결된 실행 계획이 이미 있습니다.")
    op = WorkOperation(dataset_id=dataset_id, product_id=decision.product_id, kind=kind,
        source_label="user_record" if db.get(WorkDataset, dataset_id).kind == "company" else "scenario_record",
        planned_start=payload.planned_start, planned_end=payload.planned_end,
        planned_units=units, expected_receipt_date=arrival, opening_stock=stock,
        expected_sales_units=comparison.get("expected_units_30d"),
        expected_revenue_krw=comparison.get("estimated_revenue_krw"),
        expected_profit_krw=comparison.get("estimated_gross_profit_krw"),
        discount_pct=comparison.get("discount_pct"), unit_cost_krw=cost,
        note=payload.note.strip(), **link)
    db.add(op)
    db.commit()
    return _out(op, db)


@router.get("")
def list_operations(dataset_id: int, db: Session = Depends(get_db)):
    if db.get(WorkDataset, dataset_id) is None:
        raise HTTPException(404, "작업공간을 찾지 못했습니다.")
    return [_out(op, db) for op in db.scalars(select(WorkOperation)
        .where(WorkOperation.dataset_id == dataset_id).order_by(WorkOperation.id.desc()))]


@router.post("/{operation_id}/events")
def add_event(operation_id: int, payload: AddEvent, db: Session = Depends(get_db)):
    op = db.get(WorkOperation, operation_id)
    if op is None:
        raise HTTPException(404, "실행 계획을 찾지 못했습니다.")
    if payload.client_key:
        prior = db.scalar(select(WorkOperationEvent).where(WorkOperationEvent.client_key == payload.client_key))
        if prior:
            if prior.operation_id != op.id:
                raise HTTPException(409, "다른 기록에서 사용한 요청 번호입니다.")
            return _out(op, db)
    allowed = ({"ordered", "received", "sale", "stock_count", "cancelled"} if op.kind == "replenish"
               else {"started", "finished", "sale", "stock_count", "cancelled"})
    if payload.kind not in allowed or payload.event_date < op.planned_start:
        raise HTTPException(400, "기록 종류 또는 날짜가 계획과 맞지 않습니다.")
    if op.status in {"cancelled", "received", "finished"} and payload.kind != "stock_count":
        raise HTTPException(400, "종료된 계획에는 진행 기록을 더할 수 없습니다.")
    if op.kind != "replenish" and payload.kind == "sale" and payload.event_date > op.planned_end:
        raise HTTPException(400, "행사 기간 안의 판매만 이 계획에 기록하세요.")
    if payload.kind in {"received", "sale", "stock_count"} and payload.units is None:
        raise HTTPException(400, "수량을 입력하세요.")
    current = _out(op, db)
    if payload.kind == "received" and current["received_units"] + payload.units > op.planned_units:
        raise HTTPException(400, "누적 입고가 계획 수량을 넘습니다. 계획을 수정해 새 판단으로 저장하세요.")
    db.add(WorkOperationEvent(operation_id=op.id, **payload.model_dump()))
    if payload.kind == "cancelled":
        op.status = "cancelled"
    elif payload.kind == "received":
        op.status = "received" if current["received_units"] + payload.units == op.planned_units else "partial"
    elif payload.kind == "ordered":
        op.status = "ordered"
    elif payload.kind == "started":
        op.status = "active"
    elif payload.kind == "finished":
        op.status = "finished"
    db.commit()
    return _out(op, db)
