"""Import observed H&M peer sales at 2020-08-31 and aligned 2019/2020 weeks.

Reads only date and article ID from the original archives. Existing catalog rows,
decisions, and operating assumptions are never overwritten.
"""

import argparse
import csv
import io
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import WorkCatalogProduct, WorkCatalogSalesSnapshot, WorkCatalogWeekSale, WorkDataset  # noqa: E402

AS_OF = date(2020, 8, 31)
APPAREL_GROUPS = {
    "Jersey Fancy", "Jersey Basic", "Knitwear", "Trousers", "Blouses", "Dresses Ladies",
    "Outdoor", "Trousers Denim", "Shirts", "Shorts", "Skirts", "Dressed",
    "Dresses/Skirts girls", "Woven/Jersey/Knitted mix Baby", "Special Offers",
}


def scope_of(garment_group: str) -> str:
    if garment_group == "Accessories":
        return "accessory"
    if garment_group in APPAREL_GROUPS:
        return "apparel"
    return "other"


def run(db_path: Path, articles_zip: Path, transactions_zip: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path.resolve()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        dataset = db.scalar(select(WorkDataset).where(WorkDataset.kind == "hm").order_by(WorkDataset.id.desc()))
        if dataset is None:
            raise ValueError("H&M 작업공간이 없습니다.")
        existing = db.scalar(select(func.count()).select_from(WorkCatalogSalesSnapshot).where(
            WorkCatalogSalesSnapshot.dataset_id == dataset.id, WorkCatalogSalesSnapshot.as_of_date == AS_OF)) or 0
        if existing:
            print(f"8/31 전체 상품 판매 집계 {existing:,}행이 이미 있어 유지합니다.")
            return
        catalog_count = db.scalar(select(func.count()).select_from(WorkCatalogProduct).where(
            WorkCatalogProduct.dataset_id == dataset.id)) or 0
        if not catalog_count:
            raise ValueError("전체 상품 목록이 없습니다. 기존 전체 상품 적재를 먼저 실행하세요.")

        with zipfile.ZipFile(articles_zip) as archive, archive.open("articles.csv") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            articles = {row["article_id"].encode("ascii"): (
                row["section_name"][:100], row["product_type_name"][:100],
                row["garment_group_name"][:80]) for row in reader}
        if len(articles) != catalog_count:
            raise ValueError(f"원본 상품 {len(articles):,}종과 DB 목록 {catalog_count:,}종이 다릅니다.")

        snapshots: dict[bytes, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
        weeks: Counter[tuple[bytes, int, int]] = Counter()
        checked = 0
        with zipfile.ZipFile(transactions_zip) as archive, archive.open("transactions_train.csv") as raw:
            next(raw)
            for line in raw:
                checked += 1
                day = line[:10]
                in_2019 = b"2019-07-01" <= day <= b"2019-08-31"
                in_2020 = b"2020-07-01" <= day <= b"2020-08-31"
                if not (in_2019 or in_2020):
                    continue
                parts = line.rstrip(b"\r\n").split(b",")
                if len(parts) != 5 or parts[2] not in articles:
                    raise ValueError(f"거래 {checked:,}행의 열 또는 상품번호가 원본 상품과 맞지 않습니다.")
                sku = parts[2]
                if scope_of(articles[sku][2]) != "other":
                    year = 2019 if in_2019 else 2020
                    week_index = (date.fromisoformat(day.decode("ascii")) - date(year, 7, 1)).days // 7
                    weeks[(sku, year, week_index)] += 1
                if in_2020 and day >= b"2020-08-02":
                    counts = snapshots[sku]
                    counts[4] += 1
                    if day >= b"2020-08-25":
                        counts[0] += 1
                    if b"2020-08-18" <= day <= b"2020-08-24":
                        counts[1] += 1
                    if day >= b"2020-08-18":
                        counts[2] += 1
                    if b"2020-08-04" <= day <= b"2020-08-17":
                        counts[3] += 1
                if checked % 5_000_000 == 0:
                    print(f"원본 거래 {checked:,}행 확인", flush=True)

        try:
            batch = []
            for sku, (section, category, garment_group) in articles.items():
                u7, p7, u14, p14, u30 = snapshots.get(sku, [0, 0, 0, 0, 0])
                batch.append({"dataset_id": dataset.id, "sku": sku.decode("ascii"), "as_of_date": AS_OF,
                              "scope": scope_of(garment_group), "garment_group": garment_group,
                              "section": section, "category": category, "units_7d": u7,
                              "prior_7d": p7, "units_14d": u14, "prior_14d": p14, "units_30d": u30})
                if len(batch) == 5000:
                    db.bulk_insert_mappings(WorkCatalogSalesSnapshot, batch)
                    batch.clear()
            if batch:
                db.bulk_insert_mappings(WorkCatalogSalesSnapshot, batch)
            batch = []
            for (sku, year, week_index), units in sorted(weeks.items()):
                batch.append({"dataset_id": dataset.id, "sku": sku.decode("ascii"),
                              "year": year, "week_index": week_index, "units": units})
                if len(batch) == 5000:
                    db.bulk_insert_mappings(WorkCatalogWeekSale, batch)
                    batch.clear()
            if batch:
                db.bulk_insert_mappings(WorkCatalogWeekSale, batch)
            db.commit()
        except Exception:
            db.rollback()
            raise
        print(f"완료: 상품 {len(articles):,}종, 동종 주간 기록 {len(weeks):,}행, 거래 {checked:,}행. 기준일 {AS_OF}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("md_decision_lab.db"))
    parser.add_argument("--articles", type=Path, required=True)
    parser.add_argument("--transactions", type=Path, required=True)
    args = parser.parse_args()
    run(args.db, args.articles, args.transactions)
