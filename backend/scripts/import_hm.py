"""Import a bounded, reproducible H&M sales sample without copying raw customer data.

Run from backend/: python scripts/import_hm.py --articles PATH --transactions PATH
The ZIP inputs stay outside this repository. A new dataset is created only once.
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

from sqlalchemy import select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import WorkDailySale, WorkDataset, WorkProduct  # noqa: E402

SECTIONS = ("Womens Everyday Collection", "Womens Tailoring", "Womens Jackets")
START, END = b"2019-01-01", b"2020-09-22"


def run(articles_zip: Path, transactions_zip: Path, max_per_year: int) -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.scalar(select(WorkDataset.id).where(WorkDataset.name == "H&M 실제 판매 · MD 시연")):
            print("H&M 시연 작업공간이 이미 있습니다. 기존 자료를 덮어쓰지 않았습니다.")
            return
        with zipfile.ZipFile(articles_zip) as archive, archive.open("articles.csv") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            articles = {row["article_id"].encode(): row for row in reader if row["section_name"] in SECTIONS}
        if not articles:
            raise ValueError("선택한 여성복 섹션의 상품이 없습니다.")
        print(f"선택 섹션 상품 {len(articles):,}종; 거래 파일을 한 번 읽습니다.", flush=True)
        daily: Counter[tuple[bytes, bytes, bytes]] = Counter()
        seasonal: Counter[tuple[str, bytes, bytes]] = Counter()
        scanned = 0
        with zipfile.ZipFile(transactions_zip) as archive, archive.open("transactions_train.csv") as raw:
            next(raw)
            for line in raw:
                scanned += 1
                fields = line.rstrip(b"\r\n").split(b",")
                if len(fields) != 5:
                    raise ValueError(f"거래 {scanned + 1}행의 열 수가 5개가 아닙니다.")
                day, _, article_id, _, channel = fields
                if day < START or day > END or article_id not in articles:
                    continue
                daily[(article_id, day, channel)] += 1
                if b"-07-01" <= day[4:] <= b"-09-22":
                    seasonal[(articles[article_id]["section_name"], day[:4], article_id)] += 1
                if scanned % 5_000_000 == 0:
                    print(f"거래 {scanned:,}행 확인; 일별 묶음 {len(daily):,}개", flush=True)
        chosen: set[bytes] = set()
        for section in SECTIONS:
            for year in (b"2019", b"2020"):
                ranks = [(count, article_id) for (s, y, article_id), count in seasonal.items()
                         if s == section and y == year]
                chosen.update(article_id for _, article_id in sorted(ranks, reverse=True)[:max_per_year])
        selected_days = [(key, units) for key, units in daily.items() if key[0] in chosen]
        del daily
        print(f"선정 상품 {len(chosen):,}종; 일별·채널별 기록 {len(selected_days):,}행", flush=True)
        dataset = WorkDataset(name="H&M 실제 판매 · MD 시연", kind="hm",
                              start_date=date(2019, 1, 1), end_date=date(2020, 9, 22),
                              complete_calendar=True,
                              source_note=("H&M Kaggle 거래 기록. 여성복 3개 섹션에서 2019·2020년 "
                                           f"7~9월 판매 상위 각 {max_per_year}종의 합집합. "
                                           "거래 행 수=판매 개수. 가격은 정규화 값이므로 원화 매출로 사용하지 않음. "
                                           "재고·원가·발주 정보는 제공되지 않음."))
        db.add(dataset)
        db.flush()
        product_rows = []
        for article_id in sorted(chosen):
            article = articles[article_id]
            product_rows.append({"dataset_id": dataset.id, "sku": article["article_id"],
                                 "product_code": article["product_code"],
                                 "name": article["prod_name"][:180],
                                 "category": article["product_type_name"][:100],
                                 "section": article["section_name"][:100]})
        db.bulk_insert_mappings(WorkProduct, product_rows)
        db.flush()
        ids = dict(db.execute(select(WorkProduct.sku, WorkProduct.id).where(
            WorkProduct.dataset_id == dataset.id)).all())
        batch = []
        for (article_id, day, channel), units in selected_days:
            batch.append({"product_id": ids[article_id.decode()], "sale_date": date.fromisoformat(day.decode()),
                          "channel": channel.decode(), "units": units, "revenue": None, "gross_profit": None})
            if len(batch) >= 5000:
                db.bulk_insert_mappings(WorkDailySale, batch)
                batch.clear()
        if batch:
            db.bulk_insert_mappings(WorkDailySale, batch)
        db.commit()
        print(f"완료: dataset_id={dataset.id}, 상품 {len(chosen):,}종, 일별 판매 {len(selected_days):,}행")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", type=Path, required=True)
    parser.add_argument("--transactions", type=Path, required=True)
    parser.add_argument("--max-per-year", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.max_per_year <= 200:
        parser.error("--max-per-year는 1~200 사이로 지정하세요.")
    run(args.articles, args.transactions, args.max_per_year)
