"""Isolated synthetic fashion case; never replaces an existing workspace."""

import csv
import io
import math
from math import ceil
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailySale, FashionDecision, MerchandisingContext, Product
from ..services.analysis import analyze_product

router = APIRouter(prefix="/api/fashion", tags=["Synthetic fashion case"])
CASE_DIR = Path(__file__).resolve().parents[3] / "sample_data" / "fashion_fw_case"
CASE_DATE = date(2026, 8, 31)
DECISION_TYPES = {
    "markdown_review", "live_exposure", "stock_transfer", "launch_check", "sellout_monitor", "hold",
    "option_a", "option_b",
}


class DecisionInput(BaseModel):
    sku: str
    action_type: str
    rationale: str = Field(min_length=5, max_length=1000)
    chosen_option: str | None = Field(default=None, max_length=32)
    discount_pct: float | None = Field(default=None, ge=0, le=70)
    expected_units_30d: int | None = Field(default=None, ge=0)
    purchase_units: int | None = Field(default=0, ge=0)
    estimated_revenue: float | None = None
    estimated_gross_profit: float | None = None
    estimated_remaining_stock: int | None = None
    feasible: bool | None = None


class ProductInput(BaseModel):
    stock_on_hand: int = Field(ge=0)
    inbound_units: int = Field(ge=0)
    unit_price: float = Field(ge=0)
    unit_cost: float = Field(ge=0)


class ScenarioOptionInput(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    discount_pct: float = Field(default=0, ge=0, le=70, allow_inf_nan=False)
    expected_units_30d: int = Field(ge=0, le=100000)
    purchase_units: int = Field(default=0, ge=0, le=100000)


class ScenarioComparisonInput(BaseModel):
    sku: str
    options: list[ScenarioOptionInput] = Field(min_length=2, max_length=2)


def _fashion_product(sku: str, db: Session) -> Product:
    product = db.scalar(select(Product).where(Product.sku == sku, Product.sku.like("FSH-%")))
    if product is None or db.get(MerchandisingContext, product.id) is None:
        raise HTTPException(status_code=404, detail="패션 사례 상품을 찾지 못했습니다.")
    return product


def _read(name: str) -> list[dict[str, str]]:
    with (CASE_DIR / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


@router.get("/status")
def status(db: Session = Depends(get_db)):
    count = db.scalar(select(func.count(Product.id)).where(Product.sku.like("FSH-%"))) or 0
    context_count = db.scalar(select(func.count(MerchandisingContext.product_id)).join(Product).where(Product.sku.like("FSH-%"))) or 0
    sale_count = db.scalar(select(func.count(DailySale.id)).join(Product).where(Product.sku.like("FSH-%"))) or 0
    return {"imported": count == 30 and context_count == 30 and sale_count == 1800,
            "product_count": count, "default_as_of_date": CASE_DATE,
            "source": "synthetic fashion_fw_case; not observed business results"}


@router.post("/import-sample")
def import_sample(db: Session = Depends(get_db)):
    """One-time, all-or-nothing import of the bundled three-file case."""
    existing = db.scalar(select(func.count(Product.id)).where(Product.sku.like("FSH-%"))) or 0
    if existing:
        raise HTTPException(status_code=409, detail="FSH 상품이 이미 있습니다. 기존 자료를 덮어쓰지 않았습니다.")
    try:
        products = _read("fashion_products_20260831.csv")
        sales = _read("fashion_daily_sales_20260831.csv")
        contexts = _read("fashion_merchandising_context.csv")
        product_skus = {row["sku"] for row in products}
        if len(products) != 30 or len(product_skus) != 30 or len(sales) != 1800 or len(contexts) != 30:
            raise ValueError("샘플 데이터의 행 수 또는 SKU 중복을 확인하세요.")
        if {row["sku"] for row in contexts} != product_skus or {row["sku"] for row in sales} != product_skus:
            raise ValueError("판매·기획 정보의 SKU가 상품 목록과 다릅니다.")
        product_ids = {}
        product_prices = {row["sku"]: (float(row["unit_price"]), float(row["unit_cost"])) for row in products}
        for row in products:
            values = {key: int(row[key]) for key in ("stock_on_hand", "inbound_units", "lead_time_days", "target_cover_days")}
            values.update({key: float(row[key]) for key in ("unit_price", "unit_cost")})
            if any(value < 0 for value in values.values()):
                raise ValueError(f"음수 상품값: {row['sku']}")
            product = Product(sku=row["sku"], name=row["name"], category=row["category"], **values)
            db.add(product)
            db.flush()
            product_ids[row["sku"]] = product.id
        for row in contexts:
            if row["reorderable"].lower() not in {"true", "false"}:
                raise ValueError(f"재발주 가능 여부가 잘못됐습니다: {row['sku']}")
            db.add(MerchandisingContext(
                product_id=product_ids[row["sku"]], season_group=row["season_group"],
                lifecycle_status=row["lifecycle_status"], reorderable=row["reorderable"].lower() == "true",
                launch_date=date.fromisoformat(row["launch_date"]) if row["launch_date"] else None,
                event_start_date=date.fromisoformat(row["event_start_date"]) if row["event_start_date"] else None,
                list_price=float(row["list_price"]), planning_note=row["planning_note"],
            ))
        seen = set()
        for row in sales:
            sale_date = date.fromisoformat(row["sale_date"])
            key = (row["sku"], sale_date)
            if key in seen or not date(2026, 7, 3) <= sale_date <= CASE_DATE:
                raise ValueError(f"중복 또는 범위를 벗어난 판매일: {key}")
            seen.add(key)
            units, revenue, margin = int(row["units_sold"]), float(row["revenue"]), float(row["gross_margin"])
            price, cost = product_prices[row["sku"]]
            if units < 0 or revenue < 0 or abs(revenue - units * price) > 0.01 or abs(margin - (revenue - units * cost)) > 0.01:
                raise ValueError(f"판매·매출·이익 값이 맞지 않습니다: {key}")
            db.add(DailySale(product_id=product_ids[row["sku"]], sale_date=sale_date,
                             units_sold=units, revenue=revenue, gross_margin=margin))
        if len(seen) != 30 * 60:
            raise ValueError("모든 상품에 60일치 일별 판매가 있어야 합니다.")
        db.commit()
    except (OSError, KeyError, ValueError, TypeError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"샘플 검증 실패: {exc}") from exc
    return {"imported": True, "product_count": 30, "sale_rows": 1800, "as_of_date": CASE_DATE}


@router.get("/analysis")
def analysis(as_of: date = Query(default=CASE_DATE), db: Session = Depends(get_db)):
    if as_of != CASE_DATE:
        raise HTTPException(status_code=400, detail="이 샘플의 재고 스냅샷은 2026-08-31만 있습니다. 다른 날짜 분석에는 해당 날짜의 재고가 필요합니다.")
    products = db.scalars(select(Product).where(Product.sku.like("FSH-%")).order_by(Product.sku)).all()
    if len(products) != 30:
        raise HTTPException(status_code=409, detail="먼저 패션 사례 데이터를 연결하세요.")
    items = []
    for product in products:
        current = analyze_product(product, db, as_of)
        prior_rows = db.scalars(select(DailySale).where(
            DailySale.product_id == product.id,
            DailySale.sale_date.between(as_of - timedelta(days=59), as_of - timedelta(days=30)),
        )).all()
        prior_complete = len(prior_rows) == 30
        prior_units = sum(row.units_sold for row in prior_rows) if prior_complete else None
        item = current.model_dump()
        item["prior_30d_units"] = prior_units
        item["units_change_pct"] = round((current.units_30d / prior_units - 1) * 100, 1) if prior_units else None
        item["trend_note"] = "출시 전: 전기 대비 비교 대상 아님" if current.launch_date and as_of < current.launch_date else (
            "전기 30일 자료 부족" if prior_units is None else "전기 판매 0개: 변화율 계산 불가" if prior_units == 0 else "직전 30일 대비 수량 변화; 원인은 별도 확인 필요"
        )
        items.append(item)
    summary_by_season = {}
    for season in {item["season_group"] for item in items}:
        segment = [item for item in items if item["season_group"] == season]
        revenue = sum(item["revenue_30d"] for item in segment)
        margin = sum(item["gross_margin_30d"] for item in segment)
        summary_by_season[season] = {
            "stock_cost_value": round(sum(item["stock_on_hand"] * item["unit_cost"] for item in segment), 2),
            "revenue_30d": round(revenue, 2), "gross_margin_30d": round(margin, 2),
            "gross_margin_rate_30d_pct": round(margin / revenue * 100, 1) if revenue > 0 else None,
            "margin_is_estimated": any(item["margin_is_estimated"] for item in segment),
            "attention_count": sum(item["risk"] != "healthy" for item in segment),
        }
    return {"as_of_date": as_of, "source": "합성 의류 브랜드 데이터", "currency": "KRW", "products": items,
            "summary_by_season": summary_by_season,
            "note": "현재고는 기준일 스냅샷으로 가정한 값입니다. 과거 기준일을 선택해도 과거 재고로 되돌리지 않습니다."}


@router.put("/products/{sku}/inputs")
def update_product_inputs(sku: str, payload: ProductInput, db: Session = Depends(get_db)):
    product = _fashion_product(sku, db)
    if not math.isfinite(payload.unit_price) or not math.isfinite(payload.unit_cost):
        raise HTTPException(status_code=400, detail="판매가와 원가는 유효한 숫자여야 합니다.")
    product.stock_on_hand = payload.stock_on_hand
    product.inbound_units = payload.inbound_units
    product.unit_price = payload.unit_price
    product.unit_cost = payload.unit_cost
    db.commit()
    return analyze_product(product, db, CASE_DATE)


@router.post("/sales/import")
async def import_sales_corrections(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Replace only specified SKU/date rows; validate every row before any write."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 가져올 수 있습니다.")
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("cp949")
    reader = csv.DictReader(io.StringIO(content))
    required = {"sku", "sale_date", "units_sold", "revenue"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise HTTPException(status_code=400, detail="필수 열: sku, sale_date, units_sold, revenue. gross_margin은 선택입니다.")
    parsed = []
    seen = set()
    try:
        for line, row in enumerate(reader, 2):
            sku = row["sku"].strip()
            product = _fashion_product(sku, db)
            sale_date = date.fromisoformat(row["sale_date"].strip())
            if not date(2026, 7, 3) <= sale_date <= CASE_DATE:
                raise ValueError(f"{line}행: 날짜는 2026-07-03~2026-08-31이어야 합니다.")
            key = (sku, sale_date)
            if key in seen:
                raise ValueError(f"{line}행: SKU·날짜가 중복됩니다.")
            seen.add(key)
            units = int(row["units_sold"])
            revenue = float(row["revenue"])
            margin_text = (row.get("gross_margin") or "").strip()
            margin = float(margin_text) if margin_text else None
            if units < 0 or not math.isfinite(revenue) or (margin is not None and not math.isfinite(margin)) or revenue < 0 or (margin is not None and margin > revenue) or (units == 0 and (revenue != 0 or (margin is not None and margin != 0))):
                raise ValueError(f"{line}행: 판매 수량·매출·매출총이익을 확인하세요.")
            parsed.append((product.id, sale_date, units, revenue, margin))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"판매 CSV 검증 실패: {exc}") from exc
    if not parsed:
        raise HTTPException(status_code=400, detail="판매 행이 없습니다.")
    for product_id, sale_date, units, revenue, margin in parsed:
        record = db.scalar(select(DailySale).where(DailySale.product_id == product_id, DailySale.sale_date == sale_date))
        if record is None:
            record = DailySale(product_id=product_id, sale_date=sale_date)
            db.add(record)
        record.units_sold, record.revenue, record.gross_margin = units, revenue, margin
    db.commit()
    return {"updated": len(parsed), "as_of_date": CASE_DATE}


@router.get("/markdown/{sku}")
def markdown_check(sku: str, discount_pct: float = Query(ge=0, le=70), db: Session = Depends(get_db)):
    """Arithmetic gross-profit threshold, not a sales or conversion forecast."""
    product = db.scalar(select(Product).where(Product.sku == sku, Product.sku.like("FSH-%")))
    if product is None:
        raise HTTPException(status_code=404, detail="패션 사례 상품을 찾지 못했습니다.")
    baseline = analyze_product(product, db, CASE_DATE)
    proposed_price = round(product.unit_price * (1 - discount_pct / 100), 2)
    proposed_unit_margin = proposed_price - product.unit_cost
    current_unit_margin = product.unit_price - product.unit_cost
    required_units = ceil(baseline.units_30d * current_unit_margin / proposed_unit_margin) if proposed_unit_margin > 0 else None
    return {
        "sku": sku, "discount_pct": discount_pct, "current_price": product.unit_price,
        "proposed_price": proposed_price, "unit_cost": product.unit_cost,
        "proposed_unit_gross_margin": round(proposed_unit_margin, 2),
        "proposed_gross_margin_rate_pct": round(proposed_unit_margin / proposed_price * 100, 1) if proposed_price > 0 else None,
        "proposed_unit_markup_pct": round(proposed_unit_margin / product.unit_cost * 100, 1) if product.unit_cost > 0 else None,
        "baseline_units_30d": baseline.units_30d,
        "break_even_units_30d": required_units,
        "additional_units_needed": max(required_units - baseline.units_30d, 0) if required_units is not None else None,
        "note": "상품 원가만 반영한 단순 매출총이익 기준입니다. 수요 증가, 수수료, 배송비, 반품, 세금은 예측하거나 반영하지 않습니다.",
    }


@router.post("/compare-options")
def compare_options(payload: ScenarioComparisonInput, db: Session = Depends(get_db)):
    """Compare user assumptions without altering measured sales or claiming a causal result."""
    product = _fashion_product(payload.sku, db)
    context = db.get(MerchandisingContext, product.id)
    if product.unit_cost <= 0 or product.unit_price <= 0:
        raise HTTPException(status_code=400, detail="판매가와 상품 원가를 먼저 확인하세요.")
    if not context.reorderable and any(option.purchase_units > 0 for option in payload.options):
        raise HTTPException(status_code=400, detail="이 상품은 재발주할 수 없어 추가 매입안을 비교할 수 없습니다.")
    observed = analyze_product(product, db, CASE_DATE)
    options = []
    for option in payload.options:
        price = round(product.unit_price * (1 - option.discount_pct / 100), 2)
        available = product.stock_on_hand + product.inbound_units + option.purchase_units
        shortfall = max(option.expected_units_30d - available, 0)
        feasible = shortfall == 0
        revenue = round(price * option.expected_units_30d, 2) if feasible else None
        gross_profit = round((price - product.unit_cost) * option.expected_units_30d, 2) if feasible else None
        options.append({
            "label": option.label,
            "discount_pct": option.discount_pct,
            "expected_units_30d": option.expected_units_30d,
            "purchase_units": option.purchase_units,
            "unit_price": price,
            "available_units": available,
            "shortfall_units": shortfall,
            "feasible": feasible,
            "estimated_revenue": revenue,
            "estimated_gross_profit": gross_profit,
            "estimated_gross_margin_rate_pct": round(gross_profit / revenue * 100, 1) if revenue else None,
            "estimated_remaining_stock": available - option.expected_units_30d if feasible else None,
            "purchase_cash_required": round(option.purchase_units * product.unit_cost, 2),
        })
    return {
        "sku": product.sku,
        "as_of_date": CASE_DATE,
        "observed": {"units_30d": observed.units_30d, "revenue_30d": observed.revenue_30d,
                     "gross_margin_30d": observed.gross_margin_30d},
        "snapshot": {"stock_on_hand": product.stock_on_hand, "inbound_units": product.inbound_units,
                     "unit_price": product.unit_price, "unit_cost": product.unit_cost,
                     "reorderable": context.reorderable},
        "options": options,
        "note": "판매 수량과 추가 매입은 사용자 가정입니다. 입고 예정·매입 수량이 30일 안에 판매 가능하다는 가정으로 재고 충족 여부만 확인합니다. 매출·매출총이익은 예상 계산값이며 실제 A/B 테스트 결과나 순이익이 아닙니다. 수수료·배송비·반품·광고비는 제외합니다.",
    }


def _format_decision(item: FashionDecision, sku: str) -> dict:
    return {
        "id": item.id,
        "sku": sku,
        "as_of_date": item.as_of_date,
        "action_type": item.action_type,
        "rationale": item.rationale,
        "observed_units_7d": item.observed_units_7d,
        "observed_units_30d": item.observed_units_30d,
        "assumed_stock_on_hand": item.assumed_stock_on_hand,
        "chosen_option": item.chosen_option,
        "discount_pct": item.discount_pct,
        "expected_units_30d": item.expected_units_30d,
        "purchase_units": item.purchase_units or 0,
        "estimated_revenue": item.estimated_revenue,
        "estimated_gross_profit": item.estimated_gross_profit,
        "estimated_remaining_stock": item.estimated_remaining_stock,
        "feasible": item.feasible,
        "created_at": item.created_at,
    }


@router.get("/decisions")
def list_decisions(db: Session = Depends(get_db)):
    rows = db.execute(select(FashionDecision, Product.sku).join(Product).order_by(FashionDecision.id.desc()).limit(100)).all()
    return [_format_decision(item, sku) for item, sku in rows]


@router.post("/decisions")
def create_decision(payload: DecisionInput, db: Session = Depends(get_db)):
    if payload.action_type not in DECISION_TYPES:
        raise HTTPException(status_code=400, detail="선택할 수 없는 조치입니다.")
    if len(payload.rationale.strip()) < 5:
        raise HTTPException(status_code=400, detail="판단 이유를 5자 이상 적어주세요.")
    product = db.scalar(select(Product).where(Product.sku == payload.sku, Product.sku.like("FSH-%")))
    if product is None or db.get(MerchandisingContext, product.id) is None:
        raise HTTPException(status_code=404, detail="패션 사례 상품을 찾지 못했습니다.")
    context = db.get(MerchandisingContext, product.id)
    if payload.action_type == "markdown_review" and product.unit_price <= product.unit_cost:
        raise HTTPException(status_code=400, detail="현재 판매가가 원가 이하입니다. 할인 검토 전에 가격과 원가를 확인하세요.")

    purchase_units = payload.purchase_units or 0
    if not context.reorderable and purchase_units > 0:
        raise HTTPException(status_code=400, detail="이 상품은 재발주가 불가능해 추가 매입을 반영할 수 없습니다.")

    raw_chosen = (payload.chosen_option or "").strip()
    action = payload.action_type.strip()

    if raw_chosen and raw_chosen not in {"A", "B", "hold"}:
        raise HTTPException(status_code=400, detail="선택한 안은 'A', 'B', 또는 'hold'여야 합니다.")

    # Explicit contradiction checks between action_type and chosen_option
    if raw_chosen == "A" and action != "option_a":
        raise HTTPException(status_code=400, detail=f"선택한 안(A)과 조치 유형({action})이 서로 모순됩니다.")
    if raw_chosen == "B" and action != "option_b":
        raise HTTPException(status_code=400, detail=f"선택한 안(B)과 조치 유형({action})이 서로 모순됩니다.")
    if raw_chosen == "hold" and action != "hold":
        raise HTTPException(status_code=400, detail=f"선택한 안(보류)과 조치 유형({action})이 서로 모순됩니다.")
    if action == "option_a" and raw_chosen and raw_chosen != "A":
        raise HTTPException(status_code=400, detail=f"조치 유형(option_a)과 선택한 안({raw_chosen})이 서로 모순됩니다.")
    if action == "option_b" and raw_chosen and raw_chosen != "B":
        raise HTTPException(status_code=400, detail=f"조치 유형(option_b)과 선택한 안({raw_chosen})이 서로 모순됩니다.")
    if action == "hold" and raw_chosen and raw_chosen != "hold":
        raise HTTPException(status_code=400, detail=f"조치 유형(hold)과 선택한 안({raw_chosen})이 서로 모순됩니다.")

    # Resolution for missing chosen_option (Legacy / compatibility policy)
    if not raw_chosen:
        if action == "option_a":
            chosen = "A"
        elif action == "option_b":
            chosen = "B"
        elif action == "hold":
            chosen = "hold"
        else:
            # Legacy simple actions like markdown_review, live_exposure, etc.
            chosen = None
    else:
        chosen = raw_chosen

    baseline = analyze_product(product, db, CASE_DATE)

    # Validate coherence and recompute authoritative results on the server
    if chosen == "hold":
        chosen_option = "hold"
        discount_pct = None
        expected_units_30d = None
        purchase_units = 0
        estimated_revenue = None
        estimated_gross_profit = None
        estimated_remaining_stock = None
        feasible = None
    elif chosen == "A":
        if payload.discount_pct is not None and payload.discount_pct > 0:
            raise HTTPException(status_code=400, detail="A안은 현재 가격 유지(할인율 0%)여야 합니다.")
        if purchase_units > 0:
            raise HTTPException(status_code=400, detail="A안은 추가 매입을 하지 않습니다.")
        chosen_option = "A"
        discount_pct = 0.0
        expected_units_30d = payload.expected_units_30d if payload.expected_units_30d is not None else baseline.units_30d
        purchase_units = 0

        # Authoritative server recomputation
        price = product.unit_price
        available = product.stock_on_hand + product.inbound_units
        shortfall = max(expected_units_30d - available, 0)
        feasible = (shortfall == 0)
        if feasible:
            estimated_revenue = round(price * expected_units_30d, 2)
            estimated_gross_profit = round((price - product.unit_cost) * expected_units_30d, 2)
            estimated_remaining_stock = available - expected_units_30d
        else:
            estimated_revenue = None
            estimated_gross_profit = None
            estimated_remaining_stock = None
    elif chosen == "B":
        chosen_option = "B"
        discount_pct = payload.discount_pct if payload.discount_pct is not None else 0.0
        expected_units_30d = payload.expected_units_30d if payload.expected_units_30d is not None else baseline.units_30d

        # Authoritative server recomputation
        price = round(product.unit_price * (1 - discount_pct / 100), 2)
        available = product.stock_on_hand + product.inbound_units + purchase_units
        shortfall = max(expected_units_30d - available, 0)
        feasible = (shortfall == 0)
        if feasible:
            estimated_revenue = round(price * expected_units_30d, 2)
            estimated_gross_profit = round((price - product.unit_cost) * expected_units_30d, 2)
            estimated_remaining_stock = available - expected_units_30d
        else:
            estimated_revenue = None
            estimated_gross_profit = None
            estimated_remaining_stock = None
    else:
        # Legacy action type without comparison scenario
        chosen_option = None
        discount_pct = None
        expected_units_30d = None
        purchase_units = 0
        estimated_revenue = None
        estimated_gross_profit = None
        estimated_remaining_stock = None
        feasible = None

    decision = FashionDecision(
        product_id=product.id,
        as_of_date=CASE_DATE,
        action_type=payload.action_type,
        rationale=payload.rationale.strip(),
        observed_units_7d=baseline.units_7d,
        observed_units_30d=baseline.units_30d,
        assumed_stock_on_hand=baseline.stock_on_hand,
        chosen_option=chosen_option,
        discount_pct=discount_pct,
        expected_units_30d=expected_units_30d,
        purchase_units=purchase_units,
        estimated_revenue=estimated_revenue,
        estimated_gross_profit=estimated_gross_profit,
        estimated_remaining_stock=estimated_remaining_stock,
        feasible=feasible,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return _format_decision(decision, product.sku)
