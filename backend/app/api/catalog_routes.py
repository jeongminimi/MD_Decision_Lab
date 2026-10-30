"""Search the complete product catalog without expanding the MD analysis sample."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, and_, case, func, literal, or_, select
from sqlalchemy.orm import Session, aliased

from ..database import get_db
from ..models import (WorkCatalogProduct, WorkCatalogSalesSnapshot, WorkDailySale, WorkDataset, WorkInputSnapshot,
                      WorkProduct, WorkProductInput, WorkSimLedger, WorkSimScenario)

router = APIRouter(prefix="/api/work", tags=["MD catalog"])


@router.get("/catalog")
def catalog(dataset_id: int, q: str = Query("", max_length=80), page: int = Query(1, ge=1),
            page_size: int = Query(40, ge=1, le=100), as_of: date | None = None,
            simulation: bool = False, db: Session = Depends(get_db),
            sort_by: Literal["name", "category", "section", "units_30d", "stock"] = "name",
            sort_dir: Literal["asc", "desc"] = "asc"):
    dataset = db.get(WorkDataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "작업공간을 찾을 수 없습니다.")
    day = as_of or dataset.end_date
    if not dataset.start_date <= day <= dataset.end_date:
        raise HTTPException(400, "조회 기준일은 판매 기간 안에 있어야 합니다.")

    source = WorkCatalogProduct if dataset.kind == "hm" else WorkProduct
    criteria = [source.dataset_id == dataset_id]
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        criteria.append(or_(source.sku.ilike(pattern), source.name.ilike(pattern),
                            source.category.ilike(pattern), source.section.ilike(pattern)))
    total = db.scalar(select(func.count()).select_from(source).where(*criteria)) or 0
    ordered = select(source).where(*criteria)
    if dataset.kind == "hm" and day != dataset.end_date:
        sale_at_day = aliased(WorkCatalogSalesSnapshot)
        ordered = ordered.outerjoin(sale_at_day, and_(sale_at_day.dataset_id == dataset_id,
                                                      sale_at_day.sku == source.sku,
                                                      sale_at_day.as_of_date == day))
    if sort_by in {"name", "category", "section"}:
        primary = func.lower(getattr(source, sort_by))
        order = [primary.desc() if sort_dir == "desc" else primary.asc()]
        order.extend((func.lower(source.name).asc(), source.sku.asc()))
    elif sort_by == "units_30d":
        if dataset.kind == "hm":
            sales_units = source.units_30d if day == dataset.end_date else sale_at_day.units_30d
        else:
            sales_totals = (select(WorkDailySale.product_id.label("product_id"),
                                   func.sum(WorkDailySale.units).label("units"))
                            .where(WorkDailySale.sale_date.between(day - timedelta(days=29), day))
                            .group_by(WorkDailySale.product_id).subquery())
            ordered = ordered.outerjoin(sales_totals, sales_totals.c.product_id == source.id)
            sales_units = func.coalesce(sales_totals.c.units, 0)
        order = [case((sales_units.is_(None), 1), else_=0).asc(),
                 sales_units.desc() if sort_dir == "desc" else sales_units.asc(),
                 func.lower(source.name).asc(), source.sku.asc()]
    else:
        sample = aliased(WorkProduct) if dataset.kind == "hm" else source
        if dataset.kind == "hm":
            ordered = ordered.outerjoin(sample, and_(sample.dataset_id == dataset_id,
                                                     sample.sku == source.sku))
        if dataset.kind == "hm" and simulation:
            scenario = db.scalar(select(WorkSimScenario).where(WorkSimScenario.dataset_id == dataset_id)
                                 .order_by(WorkSimScenario.id.desc()))
            if scenario is None:
                stock_units = literal(None, type_=Integer)
            else:
                ledger = aliased(WorkSimLedger)
                ordered = ordered.outerjoin(ledger, and_(ledger.scenario_id == scenario.id,
                                                         ledger.product_id == sample.id,
                                                         ledger.flow_date == scenario.as_of_date))
                stock_units = ledger.closing_stock
        else:
            snapshot = aliased(WorkInputSnapshot)
            legacy = aliased(WorkProductInput)
            ordered = ordered.outerjoin(snapshot, and_(snapshot.product_id == sample.id,
                                                       snapshot.as_of_date == day))
            ordered = ordered.outerjoin(legacy, and_(legacy.product_id == sample.id,
                                                     legacy.as_of_date == day))
            stock_units = case((snapshot.id.is_not(None), snapshot.stock_on_hand),
                               else_=legacy.stock_on_hand)
        # Unknown stock stays after measured/input stock in both directions.
        order = [case((stock_units.is_(None), 1), else_=0).asc(),
                 stock_units.desc() if sort_dir == "desc" else stock_units.asc(),
                 func.lower(source.name).asc(), source.sku.asc()]
    rows = db.scalars(ordered.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    skus = [row.sku for row in rows]
    samples = {row.sku: row for row in db.scalars(select(WorkProduct).where(
        WorkProduct.dataset_id == dataset_id, WorkProduct.sku.in_(skus))).all()} if skus else {}
    dated_sales = {row.sku: row for row in db.scalars(select(WorkCatalogSalesSnapshot).where(
        WorkCatalogSalesSnapshot.dataset_id == dataset_id,
        WorkCatalogSalesSnapshot.as_of_date == day,
        WorkCatalogSalesSnapshot.sku.in_(skus))).all()} if dataset.kind == "hm" and day != dataset.end_date and skus else {}
    product_ids = [row.id for row in samples.values()]

    sales: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    if dataset.kind != "hm" and product_ids:
        for row in db.scalars(select(WorkDailySale).where(
                WorkDailySale.product_id.in_(product_ids),
                WorkDailySale.sale_date.between(day - timedelta(days=29), day))):
            sales[row.product_id][1] += row.units
            if row.sale_date >= day - timedelta(days=13):
                sales[row.product_id][0] += row.units

    stock: dict[int, tuple[int | None, str, date]] = {}
    reviewable: set[int] = set(product_ids) if dataset.kind != "hm" or not simulation else set()
    if product_ids and dataset.kind == "hm" and simulation:
        scenario = db.scalar(select(WorkSimScenario).where(WorkSimScenario.dataset_id == dataset_id)
                             .order_by(WorkSimScenario.id.desc()))
        if scenario is not None:
            ledgers = db.scalars(select(WorkSimLedger).where(
                WorkSimLedger.scenario_id == scenario.id,
                WorkSimLedger.product_id.in_(product_ids),
                WorkSimLedger.flow_date == scenario.as_of_date)).all()
            for ledger in ledgers:
                stock[ledger.product_id] = (ledger.closing_stock, "simulation", scenario.as_of_date)
                reviewable.add(ledger.product_id)
    elif product_ids:
        snapshots = db.scalars(select(WorkInputSnapshot).where(
            WorkInputSnapshot.product_id.in_(product_ids), WorkInputSnapshot.as_of_date == day)).all()
        for entry in snapshots:
            stock[entry.product_id] = (entry.stock_on_hand, entry.source_label, day)
        remaining = set(product_ids) - set(stock)
        if remaining:
            legacy = db.scalars(select(WorkProductInput).where(
                WorkProductInput.product_id.in_(remaining), WorkProductInput.as_of_date == day)).all()
            for entry in legacy:
                stock[entry.product_id] = (entry.stock_on_hand, entry.source_label, day)

    items = []
    for row in rows:
        sample = samples.get(row.sku)
        product_id = sample.id if sample else None
        stock_value, stock_source, stock_date = stock.get(product_id, (None, "missing", day))
        dated = dated_sales.get(row.sku)
        hm_14 = row.units_14d if dataset.kind == "hm" and day == row.sales_as_of_date else dated.units_14d if dated else None
        hm_30 = row.units_30d if dataset.kind == "hm" and day == row.sales_as_of_date else dated.units_30d if dated else None
        hm_date = row.sales_as_of_date if dataset.kind == "hm" and day == row.sales_as_of_date else dated.as_of_date if dated else None
        items.append({
            "sku": row.sku, "name": row.name, "category": row.category, "section": row.section,
            "image_ref": sample.image_ref if sample else None,
            "units_14d": hm_14 if dataset.kind == "hm" else sales[product_id][0],
            "units_30d": hm_30 if dataset.kind == "hm" else sales[product_id][1],
            "sales_as_of_date": hm_date if dataset.kind == "hm" else day,
            "stock_on_hand": stock_value, "stock_source": stock_source,
            "stock_as_of_date": stock_date if stock_value is not None else None,
            "reviewable": product_id in reviewable,
        })
    return {"dataset_id": dataset_id, "total": total, "page": page, "page_size": page_size,
            "catalog_ready": dataset.kind != "hm" or total > 0, "items": items}
