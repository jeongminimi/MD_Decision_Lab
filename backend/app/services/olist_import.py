"""Import historical Olist demand without inventing inventory or product cost."""

import csv
import gzip
import hashlib
import os
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..models import DailySale, OlistImport, Product


PERIOD_START = date(2017, 1, 1)
PERIOD_END = date(2018, 8, 31)
SOURCE_FILES = (
    "olist_orders_dataset.csv.gz",
    "olist_order_items_dataset.csv.gz",
    "olist_products_dataset.csv.gz",
    "product_category_name_translation.csv.gz",
)


def default_data_dir() -> Path:
    return Path(os.environ.get("OLIST_DATA_DIR", "")) if os.environ.get("OLIST_DATA_DIR") else (
        Path(__file__).resolve().parents[4] / "Olist-E-Commerce-Data-Analysis" / "data"
    )


def _rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def _revision(data_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in SOURCE_FILES:
        with (data_dir / name).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return f"sha256:{digest.hexdigest()[:20]}"


def import_olist_demand(db: Session, data_dir: Path | None = None) -> OlistImport:
    existing = db.get(OlistImport, 1)
    if existing is not None:
        return existing
    data_dir = data_dir or default_data_dir()
    missing = [name for name in SOURCE_FILES if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Olist 원본 파일이 없습니다: {', '.join(missing)} ({data_dir})")
    if db.scalar(select(Product.id).where(Product.sku.like("OLIST-%")).limit(1)) is not None:
        raise ValueError("OLIST- 상품 코드가 이미 있습니다. 원본 데이터와 충돌하지 않도록 가져오기를 중단했습니다.")

    delivered: dict[str, date] = {}
    for row in _rows(data_dir / SOURCE_FILES[0]):
        if row["order_status"] != "delivered":
            continue
        try:
            purchase_date = date.fromisoformat(row["order_purchase_timestamp"][:10])
        except ValueError:
            continue
        if PERIOD_START <= purchase_date <= PERIOD_END:
            delivered[row["order_id"]] = purchase_date

    category_names = {
        row["product_category_name"]: row["product_category_name_english"]
        for row in _rows(data_dir / SOURCE_FILES[3])
    }
    categories = {
        row["product_id"]: category_names.get(row["product_category_name"], row["product_category_name"] or "unknown")
        for row in _rows(data_dir / SOURCE_FILES[2])
    }

    daily: dict[tuple[str, date], list[float]] = defaultdict(lambda: [0, 0.0])
    totals: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    item_count = 0
    for row in _rows(data_dir / SOURCE_FILES[1]):
        purchase_date = delivered.get(row["order_id"])
        if purchase_date is None:
            continue
        product_id = row["product_id"]
        price = float(row["price"])
        if not product_id or price < 0:
            continue
        daily[(product_id, purchase_date)][0] += 1
        daily[(product_id, purchase_date)][1] += price
        totals[product_id][0] += 1
        totals[product_id][1] += price
        item_count += 1

    if not daily:
        raise ValueError("선택한 기간의 배송 완료 주문 항목을 찾지 못했습니다.")
    product_rows = [
        {
            "sku": f"OLIST-{product_id}",
            "name": f"{categories.get(product_id, 'unknown')} · {product_id[:8]}",
            "category": categories.get(product_id, "unknown"),
            "stock_on_hand": 0,
            "inbound_units": 0,
            "lead_time_days": 0,
            "target_cover_days": 0,
            "unit_price": round(amount / count, 2),
            "unit_cost": 0,
        }
        for product_id, (count, amount) in sorted(totals.items())
    ]

    try:
        for start in range(0, len(product_rows), 1000):
            db.execute(insert(Product), product_rows[start:start + 1000])
        product_ids = {
            product.sku: product.id
            for product in db.scalars(select(Product).where(Product.sku.like("OLIST-%")))
        }
        sale_rows = [
            {
                "product_id": product_ids[f"OLIST-{product_id}"],
                "sale_date": sale_date,
                "units_sold": int(values[0]),
                "revenue": round(values[1], 2),
                "gross_margin": None,
            }
            for (product_id, sale_date), values in sorted(daily.items())
        ]
        for start in range(0, len(sale_rows), 1000):
            db.execute(insert(DailySale), sale_rows[start:start + 1000])
        result = OlistImport(
            id=1, source_revision=_revision(data_dir), period_start=PERIOD_START,
            period_end=PERIOD_END, order_count=len(delivered), item_count=item_count,
            product_count=len(product_rows),
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result
    except Exception:
        db.rollback()
        raise
