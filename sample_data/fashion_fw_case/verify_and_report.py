"""Validate the bundled synthetic case against the actual backend rules."""

import csv
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.fashion_routes import CASE_DATE, analysis, import_sample  # noqa: E402
from app.database import Base  # noqa: E402

HERE = Path(__file__).resolve().parent


def read_csv(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


products = read_csv("fashion_products_20260831.csv")
sales = read_csv("fashion_daily_sales_20260831.csv")
contexts = read_csv("fashion_merchandising_context.csv")
errors = []
product_ids = [row["sku"] for row in products]
context_ids = [row["sku"] for row in contexts]
if len(products) != 30 or len(sales) != 1800 or len(contexts) != 30:
    errors.append("Expected 30 products, 1,800 daily sales rows, and 30 context rows")
if len(set(product_ids)) != len(product_ids) or set(product_ids) != set(context_ids):
    errors.append("Product and context SKUs are not unique and identical")
product_map = {row["sku"]: row for row in products}
seen = set()
expected_dates = {CASE_DATE - timedelta(days=offset) for offset in range(60)}
for row in sales:
    key = (row["sku"], date.fromisoformat(row["sale_date"]))
    if row["sku"] not in product_map or key in seen or key[1] not in expected_dates:
        errors.append(f"Unknown, duplicate, or out-of-period sale: {key}")
        continue
    seen.add(key)
    product = product_map[row["sku"]]
    units = int(row["units_sold"])
    revenue = float(row["revenue"])
    margin = float(row["gross_margin"])
    if units < 0 or abs(revenue - units * float(product["unit_price"])) > 0.01 or abs(margin - (revenue - units * float(product["unit_cost"]))) > 0.01:
        errors.append(f"Revenue or margin mismatch: {key}")
if len(seen) != 30 * 60:
    errors.append("Every product needs one row for every day in the 60-day period")
for row in contexts:
    list_price, current_price = float(row["list_price"]), float(row["current_price"])
    if list_price <= 0 or abs(float(row["discount_pct"]) - round((1 - current_price / list_price) * 100, 1)) > 0.15:
        errors.append(f"Discount mismatch: {row['sku']}")
if errors:
    raise SystemExit("QA failed:\n" + "\n".join(errors[:20]))

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
with Session(engine) as db:
    imported = import_sample(db)
    results = {item["sku"]: item for item in analysis(CASE_DATE, db)["products"]}
engine.dispose()
counts = Counter(item["risk"] for item in results.values())
summer, fall, winter = (results[sku] for sku in ("FSH-SS-001", "FSH-FW-001", "FSH-EV-001"))
if winter["suggested_replenishment_units"] is not None or fall["suggested_replenishment_units"] is not None:
    raise SystemExit("QA failed: reorder or prelaunch guard did not hold")

report = f"""# 패션 F/W 합성 데이터 검증

이 자료는 실제 브랜드 실적이 아닌 **가상 연습 데이터**입니다. 기준일은 {CASE_DATE}이며 재고는 해당 날짜의 단일 스냅샷입니다. 분석은 실제 백엔드 규칙을 임시 메모리 DB에서 실행해 검증했습니다. 사용자의 저장된 DB는 수정하지 않았습니다.

| 파일 | 행 수 | 결과 |
|---|---:|---|
| 상품 | {len(products)} | SKU 중복 없음 |
| 일별 판매 | {len(sales)} | SKU별 60일 전수, 매출·매출총이익 산식 확인 |
| 시즌 기획 | {len(contexts)} | 상품 SKU와 1:1 일치, 할인율 확인 |

위험 분포: 과잉재고 {counts['overstock_risk']}개, 판매 둔화 {counts['slow_moving']}개, 출시 전·자료 부족 {counts['data_insufficient']}개, 품절 위험 {counts['stockout_risk']}개.

| 대표 상품 | 최근 7일 / 30일 판매 | 현재고 | 재고 커버 | 실제 앱의 다음 검토 |
|---|---:|---:|---:|---|
| 여름 잔여 FSH-SS-001 | {summer['units_7d']} / {summer['units_30d']}개 | {summer['stock_on_hand']}개 | {summer['days_of_cover']}일 | {summer['recommendation']} |
| 가을 신상 FSH-FW-001 | {fall['units_7d']} / {fall['units_30d']}개 | {fall['stock_on_hand']}개 | 계산 불가 | {fall['recommendation']} |
| 작년 겨울 행사 FSH-EV-001 | {winter['units_7d']} / {winter['units_30d']}개 | {winter['stock_on_hand']}개 | {winter['days_of_cover']}일 | {winter['recommendation']} |

겨울 행사 상품은 재발주 불가이므로 추가 매입 수량을 내지 않습니다. 가을 신상은 출시 전이므로 판매 0개를 부진으로 판정하지 않습니다. 행사 이후 수요 유지, 할인 효과, 실제 판매율, 조치 후 매출 상승은 이 자료로 증명할 수 없습니다. 자세한 판단 범위는 `docs/FASHION_CASE.md`에 있습니다.
"""
(HERE / "DATA_QA.md").write_text(report, encoding="utf-8")
print(f"QA PASS: {imported['product_count']} products, {imported['sale_rows']} sales rows; {dict(counts)}")
