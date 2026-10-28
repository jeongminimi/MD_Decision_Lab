import csv
import io
import math
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import DailySale, OlistImport, Product, ScenarioStock, SimulationScenario
from ..services.analysis import analyze_product
from ..services.olist_import import import_olist_demand

router = APIRouter(prefix="/api/olist", tags=["Olist demand + simulation"])


def _import_meta(source: OlistImport | None):
    if source is None:
        return {"imported": False}
    return {
        "imported": True, "source_revision": source.source_revision,
        "period_start": source.period_start, "period_end": source.period_end,
        "order_count": source.order_count, "item_count": source.item_count,
        "product_count": source.product_count, "imported_at": source.imported_at,
        "demand_definition": "delivered orders; one order_items row = one unit; item price excludes freight; BRL",
    }


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return _import_meta(db.get(OlistImport, 1))


@router.post("/import")
def import_data(db: Session = Depends(get_db)):
    try:
        return _import_meta(import_olist_demand(db))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _top_products(db: Session, as_of: date, limit: int = 20):
    since = as_of - timedelta(days=29)
    stmt = (
        select(Product.id, Product.sku, Product.name, Product.category,
               func.sum(DailySale.units_sold).label("units_30d"),
               func.sum(DailySale.revenue).label("revenue_30d"))
        .join(DailySale, DailySale.product_id == Product.id)
        .where(Product.sku.like("OLIST-%"), DailySale.sale_date.between(since, as_of))
        .group_by(Product.id)
        .order_by(func.sum(DailySale.units_sold).desc(), Product.sku)
        .limit(limit)
    )
    return [dict(row._mapping) for row in db.execute(stmt)]


@router.get("/top-products")
def top_products(limit: int = 20, db: Session = Depends(get_db)):
    source = db.get(OlistImport, 1)
    if source is None:
        raise HTTPException(status_code=409, detail="Olist 판매 데이터를 먼저 가져오세요.")
    return {"as_of_date": source.period_end, "currency": "BRL", "products": _top_products(db, source.period_end, min(max(limit, 1), 100))}


@router.get("/scenario-template")
def scenario_template(db: Session = Depends(get_db)):
    source = db.get(OlistImport, 1)
    if source is None:
        raise HTTPException(status_code=409, detail="Olist 판매 데이터를 먼저 가져오세요.")
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["scenario_name", "as_of_date", "sku", "stock_on_hand", "inbound_units", "lead_time_days", "target_cover_days", "unit_cost"])
    for item in _top_products(db, source.period_end):
        writer.writerow(["Olist 재고 시뮬레이션", source.period_end.isoformat(), item["sku"], "", "", "", "", ""])
    return Response(
        content="\ufeff" + stream.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="olist_scenario_template.csv"'},
    )


@router.post("/scenarios/import")
async def import_scenario(file: UploadFile = File(...), db: Session = Depends(get_db)):
    source = db.get(OlistImport, 1)
    if source is None:
        raise HTTPException(status_code=409, detail="Olist 판매 데이터를 먼저 가져오세요.")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 입력할 수 있습니다.")
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=400, detail="시나리오 CSV는 2MB 이하여야 합니다.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949")
    reader = csv.DictReader(io.StringIO(text))
    required = {"scenario_name", "as_of_date", "sku", "stock_on_hand", "inbound_units", "lead_time_days", "target_cover_days", "unit_cost"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise HTTPException(status_code=400, detail="시나리오 CSV 필수 열이 부족합니다. 템플릿을 내려받아 사용하세요.")

    parsed, errors, identity, seen = [], [], None, set()
    for line_no, row in enumerate(reader, 2):
        try:
            name = (row.get("scenario_name") or "").strip()
            as_of = date.fromisoformat((row.get("as_of_date") or "").strip())
            sku = (row.get("sku") or "").strip()
            if not name or len(name) > 120 or not sku.startswith("OLIST-"):
                raise ValueError("시나리오명 또는 OLIST- 상품 코드를 확인하세요.")
            if not source.period_start + timedelta(days=29) <= as_of <= source.period_end:
                raise ValueError("기준일은 Olist 데이터 기간의 완전한 30일 안에 있어야 합니다.")
            if identity is None:
                identity = (name, as_of)
            if identity != (name, as_of):
                raise ValueError("파일 안의 시나리오명과 기준일은 모두 같아야 합니다.")
            if sku in seen:
                raise ValueError("같은 SKU가 중복됐습니다.")
            seen.add(sku)
            product = db.scalar(select(Product).where(Product.sku == sku))
            if product is None:
                raise ValueError(f"Olist 상품을 찾지 못했습니다: {sku}")
            values = {key: int(row[key]) for key in ("stock_on_hand", "inbound_units", "lead_time_days", "target_cover_days")}
            cost = float(row["unit_cost"])
            if any(value < 0 for value in values.values()) or values["target_cover_days"] == 0 or not math.isfinite(cost) or cost <= 0:
                raise ValueError("재고·일수는 0 이상, 목표 보유일과 원가는 0보다 커야 합니다.")
            parsed.append((product.id, values, cost))
        except (ValueError, TypeError, KeyError) as exc:
            if len(errors) < 8:
                errors.append(f"{line_no}행: {exc}")
    if errors or not parsed:
        raise HTTPException(status_code=400, detail="; ".join(errors) if errors else "시나리오 데이터가 비어 있습니다.")

    scenario = SimulationScenario(name=identity[0], as_of_date=identity[1])
    db.add(scenario)
    db.flush()
    for product_id, values, cost in parsed:
        db.add(ScenarioStock(scenario_id=scenario.id, product_id=product_id, unit_cost=cost, **values))
    db.commit()
    return {"scenario_id": scenario.id, "name": scenario.name, "as_of_date": scenario.as_of_date, "product_count": len(parsed)}


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = db.scalars(select(SimulationScenario).options(selectinload(SimulationScenario.stocks)).order_by(SimulationScenario.id.desc())).all()
    return [{"id": item.id, "name": item.name, "as_of_date": item.as_of_date, "product_count": len(item.stocks)} for item in scenarios]


@router.get("/scenarios/{scenario_id}")
def scenario_detail(scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.scalar(
        select(SimulationScenario).where(SimulationScenario.id == scenario_id)
        .options(selectinload(SimulationScenario.stocks).selectinload(ScenarioStock.product))
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail="시나리오를 찾지 못했습니다.")
    analyses = [analyze_product(stock.product, db, scenario.as_of_date, stock).model_dump() for stock in scenario.stocks]
    analyses.sort(key=lambda item: (item["risk"] not in {"out_of_stock", "stockout_risk", "overstock_risk"}, -item["revenue_30d"]))
    return {
        "id": scenario.id, "name": scenario.name, "as_of_date": scenario.as_of_date,
        "currency": "BRL", "demand_source": "Olist delivered order items",
        "inventory_source": "user-entered simulation", "margin_source": "observed revenue minus simulated unit cost",
        "products": analyses,
    }


@router.get("/scenarios/{scenario_id}/export.csv")
def export_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Export decisions with observed-vs-assumed provenance for portfolio review."""
    detail = scenario_detail(scenario_id, db)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow([
        "scenario_id", "scenario_name", "as_of_date", "currency", "sku", "product_name",
        "observed_units_7d", "observed_units_30d", "sales_days_30d", "observed_revenue_30d",
        "assumed_stock_on_hand", "assumed_inbound_units", "assumed_unit_cost",
        "assumed_lead_time_days", "assumed_target_cover_days", "demand_basis",
        "decision_daily_units", "estimated_days_of_cover", "risk", "recommendation",
        "suggested_replenishment_units", "estimated_gross_margin_30d", "demand_explanation",
        "data_warnings", "recommendation_reason", "demand_source", "inventory_source",
    ])

    def safe(value):
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    for item in detail["products"]:
        writer.writerow([safe(value) for value in [
            detail["id"], detail["name"], detail["as_of_date"], detail["currency"],
            item["sku"], item["name"], item["units_7d"], item["units_30d"],
            item["sales_days_30d"], item["revenue_30d"], item["stock_on_hand"],
            item["inbound_units"], item["unit_cost"], item["lead_time_days"],
            item["target_cover_days"], item["demand_basis"], item["decision_daily_units"],
            item["days_of_cover"], item["risk_label"], item["recommendation"],
            item["suggested_replenishment_units"], item["gross_margin_30d"],
            item["demand_explanation"], " | ".join(item["data_warnings"]),
            item["recommendation_reason"], detail["demand_source"], detail["inventory_source"],
        ]])
    return Response(
        content="\ufeff" + stream.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="olist_scenario_{scenario_id}.csv"'},
    )


@router.get("/scenarios/{scenario_id}/compare")
def compare_scenarios(scenario_id: int, against_id: int, db: Session = Depends(get_db)):
    """Compare inventory assumptions under exactly the same observed demand window."""
    left = db.scalar(
        select(SimulationScenario).where(SimulationScenario.id == scenario_id)
        .options(selectinload(SimulationScenario.stocks).selectinload(ScenarioStock.product))
    )
    right = db.scalar(
        select(SimulationScenario).where(SimulationScenario.id == against_id)
        .options(selectinload(SimulationScenario.stocks).selectinload(ScenarioStock.product))
    )
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="비교할 시나리오를 찾지 못했습니다.")
    if left.id == right.id:
        raise HTTPException(status_code=400, detail="서로 다른 시나리오를 선택하세요.")
    left_stocks = {item.product_id: item for item in left.stocks}
    right_stocks = {item.product_id: item for item in right.stocks}
    if left.as_of_date != right.as_of_date or left_stocks.keys() != right_stocks.keys():
        raise HTTPException(status_code=400, detail="같은 기준일과 같은 상품으로 만든 시나리오만 비교할 수 있습니다.")

    rows = []
    for product_id in sorted(left_stocks):
        baseline, candidate = left_stocks[product_id], right_stocks[product_id]
        old = analyze_product(baseline.product, db, left.as_of_date, baseline)
        new = analyze_product(candidate.product, db, right.as_of_date, candidate)
        rows.append({
            "sku": old.sku, "name": old.name, "observed_units_30d": old.units_30d,
            "observed_revenue_30d": old.revenue_30d,
            "baseline_risk": old.risk, "candidate_risk": new.risk,
            "baseline_stock": baseline.stock_on_hand, "candidate_stock": candidate.stock_on_hand,
            "baseline_cover": old.days_of_cover, "candidate_cover": new.days_of_cover,
            "baseline_stock_value": round(baseline.stock_on_hand * baseline.unit_cost, 2),
            "candidate_stock_value": round(candidate.stock_on_hand * candidate.unit_cost, 2),
            "baseline_replenishment": old.suggested_replenishment_units or 0,
            "candidate_replenishment": new.suggested_replenishment_units or 0,
        })

    def summary(prefix: str):
        return {
            "stockout_count": sum(row[f"{prefix}_risk"] in {"out_of_stock", "stockout_risk"} for row in rows),
            "overstock_count": sum(row[f"{prefix}_risk"] == "overstock_risk" for row in rows),
            "stock_units": sum(row[f"{prefix}_stock"] for row in rows),
            "stock_value": round(sum(row[f"{prefix}_stock_value"] for row in rows), 2),
            "suggested_replenishment_units": sum(row[f"{prefix}_replenishment"] for row in rows),
        }

    return {
        "baseline": {"id": left.id, "name": left.name, **summary("baseline")},
        "candidate": {"id": right.id, "name": right.name, **summary("candidate")},
        "as_of_date": left.as_of_date, "currency": "BRL",
        "interpretation": "동일한 과거 판매량에 다른 재고 가정을 적용한 결과입니다. 실제 매출 변화나 조치 효과가 아닙니다.",
        "products": rows,
    }
