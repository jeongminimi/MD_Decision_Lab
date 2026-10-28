import csv
import io
import math
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailySale, MDAction, Product
from ..schemas import ActionCreate, ActionOut, ProductAnalysis, SaleImportResult
from ..services.analysis import RISK_LABELS, analyze_product
from ..services.action_outcome import evaluate_action

router = APIRouter(prefix="/api")


def action_out(action: MDAction) -> ActionOut:
    return ActionOut(
        id=action.id, product_id=action.product_id, product_name=action.product.name,
        sku=action.product.sku, action_type=action.action_type, note=action.note,
        status=action.status, stock_before=action.stock_before,
        units_30d_before=action.units_30d_before, revenue_30d_before=action.revenue_30d_before,
        created_at=action.created_at,
    )


@router.get("/health")
def health():
    return {"status": "ok", "service": "MD Decision Lab API"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    products = db.scalars(select(Product).where(~Product.sku.like("OLIST-%"), ~Product.sku.like("FSH-%")).order_by(Product.sku)).all()
    analyses = [analyze_product(product, db) for product in products]
    counts = {risk: sum(1 for item in analyses if item.risk == risk) for risk in RISK_LABELS}
    total_revenue = sum(item.revenue_30d for item in analyses)
    total_margin = sum(item.gross_margin_30d for item in analyses)
    return {
        "product_count": len(analyses),
        "risk_counts": counts,
        "revenue_30d": round(total_revenue, 2),
        "gross_margin_30d": round(total_margin, 2),
        "gross_margin_rate_30d_pct": round(total_margin / total_revenue * 100, 1) if total_revenue > 0 else None,
        "units_30d": sum(item.units_30d for item in analyses),
        "attention_count": counts["out_of_stock"] + counts["stockout_risk"] + counts["overstock_risk"],
        "demo_data": True,
    }


@router.get("/products", response_model=list[ProductAnalysis])
def list_products(q: str = "", risk: str = "all", db: Session = Depends(get_db)):
    stmt = select(Product).where(~Product.sku.like("OLIST-%"), ~Product.sku.like("FSH-%")).order_by(Product.sku)
    if q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where((Product.name.ilike(pattern)) | (Product.sku.ilike(pattern)) | (Product.category.ilike(pattern)))
    products = db.scalars(stmt).all()
    analyses = [analyze_product(product, db) for product in products]
    if risk != "all":
        analyses = [item for item in analyses if item.risk == risk]
    return analyses


@router.get("/products/{product_id}")
def product_detail(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    analysis = analyze_product(product, db)
    actions = db.scalars(select(MDAction).where(MDAction.product_id == product_id).order_by(MDAction.created_at.desc())).all()
    return {"analysis": analysis, "actions": [action_out(action) for action in actions]}


@router.post("/actions", response_model=ActionOut)
def create_action(payload: ActionCreate, db: Session = Depends(get_db)):
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    analysis = analyze_product(product, db)
    action = MDAction(
        product_id=product.id, action_type=payload.action_type, note=payload.note,
        status="planned", stock_before=product.stock_on_hand,
        units_30d_before=analysis.units_30d, revenue_30d_before=analysis.revenue_30d,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action_out(action)


@router.get("/actions", response_model=list[ActionOut])
def list_actions(db: Session = Depends(get_db)):
    actions = db.scalars(select(MDAction).order_by(MDAction.created_at.desc()).limit(50)).all()
    return [action_out(action) for action in actions]


@router.post("/actions/{action_id}/complete", response_model=ActionOut)
def complete_action(action_id: int, db: Session = Depends(get_db)):
    action = db.get(MDAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    if action.completed_at is None:
        action.status = "completed"
        action.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(action)
    return action_out(action)


@router.get("/actions/{action_id}/outcome")
def action_outcome(action_id: int, db: Session = Depends(get_db)):
    action = db.get(MDAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    return evaluate_action(action, db)


@router.post("/import/sales", response_model=SaleImportResult)
async def import_sales(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 가져올 수 있습니다.")
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    required = {"sku", "sale_date", "units_sold", "revenue"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(status_code=400, detail="필수 컬럼은 sku, sale_date, units_sold, revenue입니다. gross_margin은 선택입니다.")
    imported, rejected, messages = 0, 0, []
    for line_no, row in enumerate(reader, start=2):
        try:
            product = db.scalar(select(Product).where(Product.sku == row["sku"].strip()))
            if product is None:
                raise ValueError(f"등록된 SKU가 아닙니다: {row['sku']}")
            sale_date = date.fromisoformat(row["sale_date"].strip())
            units = int(row["units_sold"])
            revenue = float(row["revenue"])
            margin = float(row["gross_margin"]) if row.get("gross_margin", "").strip() else None
            if units < 0 or revenue < 0:
                raise ValueError("판매 수량과 매출은 음수일 수 없습니다.")
            sale = db.scalar(select(DailySale).where(DailySale.product_id == product.id, DailySale.sale_date == sale_date))
            if sale is None:
                sale = DailySale(product_id=product.id, sale_date=sale_date)
                db.add(sale)
            sale.units_sold, sale.revenue, sale.gross_margin = units, revenue, margin
            imported += 1
        except (ValueError, TypeError) as exc:
            rejected += 1
            if len(messages) < 8:
                messages.append(f"{line_no}행: {exc}")
    db.commit()
    return SaleImportResult(imported=imported, rejected=rejected, messages=messages)


@router.post("/import/products", response_model=SaleImportResult)
async def import_products(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upsert the catalog and current inventory without deleting products or history."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 가져올 수 있습니다.")
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    required = {"sku", "name", "category", "stock_on_hand", "inbound_units", "lead_time_days", "target_cover_days", "unit_price", "unit_cost"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(status_code=400, detail="필수 컬럼을 확인하세요. docs/CSV_IMPORT.md에 상품 CSV 형식이 있습니다.")

    imported, rejected, messages = 0, 0, []
    for line_no, row in enumerate(reader, start=2):
        try:
            sku = (row.get("sku") or "").strip()
            name = (row.get("name") or "").strip()
            category = (row.get("category") or "").strip() or "기타"
            if not sku or len(sku) > 40 or not name or len(name) > 160 or len(category) > 80:
                raise ValueError("SKU·상품명·카테고리 길이 또는 필수 입력을 확인하세요.")
            values = {
                "stock_on_hand": int(row["stock_on_hand"]),
                "inbound_units": int(row["inbound_units"]),
                "lead_time_days": int(row["lead_time_days"]),
                "target_cover_days": int(row["target_cover_days"]),
                "unit_price": float(row["unit_price"]),
                "unit_cost": float(row["unit_cost"]),
            }
            if any(value < 0 for key, value in values.items() if key not in {"unit_price", "unit_cost"}):
                raise ValueError("재고·입고·리드타임·목표 보유일은 음수일 수 없습니다.")
            if any(not math.isfinite(values[key]) or values[key] < 0 for key in ("unit_price", "unit_cost")):
                raise ValueError("판매가와 원가는 0 이상의 유효한 숫자여야 합니다.")
            product = db.scalar(select(Product).where(Product.sku == sku))
            if product is None:
                product = Product(sku=sku, name=name, category=category)
                db.add(product)
            product.name, product.category = name, category
            for key, value in values.items():
                setattr(product, key, value)
            imported += 1
        except (ValueError, TypeError) as exc:
            rejected += 1
            if len(messages) < 8:
                messages.append(f"{line_no}행: {exc}")
    db.commit()
    return SaleImportResult(imported=imported, rejected=rejected, messages=messages)


