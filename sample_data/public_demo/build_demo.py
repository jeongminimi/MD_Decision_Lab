"""Create upload-ready, entirely synthetic fashion data for the public demo.

This reads only the tracked fashion_fw_case files. It never reads H&M/Kaggle data.
Run from any directory: python sample_data/public_demo/build_demo.py
"""

import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fashion_fw_case"
OUTPUT = Path(__file__).resolve().parent
SNAPSHOT = "2026-08-31"
OPENING = "2026-07-03"


def read(name):
    with (SOURCE / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write(name, columns, rows):
    with (OUTPUT / name).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def money(value):
    amount = Decimal(value)
    if amount != amount.to_integral_value():
        raise ValueError(f"Non-integer KRW value: {value}")
    return int(amount)


def main():
    products = read("fashion_products_realistic_v2.csv")
    sales = read("fashion_daily_sales_realistic_v2.csv")
    context = {row["sku"]: row for row in read("fashion_merchandising_context.csv")}
    flow = read("fashion_stock_flow_2026.csv")
    assert len(products) == 30 and len(sales) == 1800 and len(flow) == 1800
    assert len(context) == 30
    assert {row["sku"] for row in products} == set(context)

    opening_stock = {}
    receipts = Counter()
    closing_stock = {}
    for row in flow:
        sku = row["sku"]
        if row["date"] == OPENING:
            opening_stock[sku] = int(row["opening_stock"])
        if row["date"] == SNAPSHOT:
            closing_stock[sku] = int(row["closing_stock"])
        assert all(int(row[key]) == 0 for key in (
            "customer_returns", "supplier_returns", "writeoffs", "adjustments"
        )), "Demo import cannot represent non-receipt stock changes"
        receipts[sku] += int(row["receipts"])

    sold = Counter()
    sale_days = defaultdict(set)
    sale_rows = []
    for row in sales:
        sku = row["sku"]
        day = row["sale_date"]
        sold[sku] += int(row["units_sold"])
        sale_days[sku].add(day)
        sale_rows.append({
            "sku": sku, "sale_date": day, "units_sold": row["units_sold"],
            "revenue": money(row["revenue"]),
            "gross_margin": money(row["gross_margin"]), "channel": "가상 온라인",
        })

    lifecycle = {"clearance": "summer_clearance", "upcoming": "fall_prelaunch",
                 "event_clearance": "winter_carryover"}
    product_rows = []
    for row in products:
        sku = row["sku"]
        assert len(sale_days[sku]) == 60
        assert min(sale_days[sku]) == OPENING and max(sale_days[sku]) == SNAPSHOT
        assert opening_stock[sku] + receipts[sku] - sold[sku] == closing_stock[sku]
        assert closing_stock[sku] == int(row["stock_on_hand"])
        status = context[sku]["lifecycle_status"]
        inbound = int(row["inbound_units"])
        product_rows.append({
            "sku": sku, "name": row["name"], "category": row["category"],
            "section": "여성복 (가상)", "stock_on_hand": row["stock_on_hand"],
            "inbound_units": inbound, "inbound_date": "2026-09-01" if inbound else "",
            "lead_time_days": row["lead_time_days"],
            "unit_price_krw": money(row["unit_price"]),
            "unit_cost_krw": money(row["unit_cost"]),
            "reorderable": context[sku]["reorderable"],
            "lifecycle": lifecycle[status],
            "opening_stock": opening_stock[sku], "opening_date": OPENING,
            "received_units": receipts[sku],
        })

    write("products.csv", list(product_rows[0]), product_rows)
    write("sales.csv", list(sale_rows[0]), sale_rows)
    print(f"가상 공개 데모 생성 완료: 상품 {len(product_rows)}종, 일별 판매 {len(sale_rows)}행")


if __name__ == "__main__":
    main()
