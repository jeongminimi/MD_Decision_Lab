"""Add the full H&M article catalog and recent sales counts without changing the MD sample.

Run from backend/ with --articles and --transactions pointing to the original ZIP files.
Only article IDs and transaction dates are read; customer IDs are never stored.
An existing catalog is left untouched.
"""

import argparse
import csv
import io
import sys
import zipfile
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import WorkCatalogProduct, WorkDataset  # noqa: E402


def run(articles_zip: Path, transactions_zip: Path) -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        dataset = db.scalar(select(WorkDataset).where(WorkDataset.kind == "hm")
                            .order_by(WorkDataset.id.desc()))
        if dataset is None:
            raise ValueError("먼저 H&M 시연 작업공간을 연결하세요.")
        present = db.scalar(select(func.count()).select_from(WorkCatalogProduct).where(
            WorkCatalogProduct.dataset_id == dataset.id)) or 0
        if present:
            print(f"기존 전체 상품 {present:,}종을 유지했습니다. 새로 적재하지 않았습니다.")
            return

        with zipfile.ZipFile(articles_zip) as archive, archive.open("articles.csv") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            articles = [(row["article_id"], row["prod_name"][:180],
                         row["product_type_name"][:100], row["section_name"][:100]) for row in reader]
        article_ids = {sku.encode("ascii") for sku, *_ in articles}
        if len(article_ids) != len(articles):
            raise ValueError("상품 파일에 중복 상품 ID가 있습니다.")

        end = dataset.end_date
        start_30 = (end - timedelta(days=29)).isoformat().encode("ascii")
        start_14 = (end - timedelta(days=13)).isoformat().encode("ascii")
        last = end.isoformat().encode("ascii")
        units_14: Counter[bytes] = Counter()
        units_30: Counter[bytes] = Counter()
        scanned = 0
        with zipfile.ZipFile(transactions_zip) as archive, archive.open("transactions_train.csv") as raw:
            next(raw)
            for line in raw:
                scanned += 1
                day, _, sku, _, _ = line.rstrip(b"\r\n").split(b",")
                if start_30 <= day <= last and sku in article_ids:
                    units_30[sku] += 1
                    if day >= start_14:
                        units_14[sku] += 1
                if scanned % 5_000_000 == 0:
                    print(f"거래 {scanned:,}행 확인", flush=True)

        batch = []
        for sku, name, category, section in articles:
            key = sku.encode("ascii")
            batch.append({"dataset_id": dataset.id, "sku": sku, "name": name,
                          "category": category, "section": section,
                          "units_14d": units_14[key], "units_30d": units_30[key],
                          "sales_as_of_date": end})
            if len(batch) == 5000:
                db.bulk_insert_mappings(WorkCatalogProduct, batch)
                batch.clear()
        if batch:
            db.bulk_insert_mappings(WorkCatalogProduct, batch)
        db.commit()
        print(f"전체 상품 {len(articles):,}종, 거래 {scanned:,}행 확인 완료. 판매 기준일 {end}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", type=Path, required=True)
    parser.add_argument("--transactions", type=Path, required=True)
    args = parser.parse_args()
    run(args.articles, args.transactions)
