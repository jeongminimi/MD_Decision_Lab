"""Build reproducible synthetic stock flows and prior-season comparables.

The original sample sales and product files remain the source of truth. These
additional rows are constructed examples, never observed company records.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
START = date(2026, 7, 3)
END = date(2026, 8, 31)


def read(name):
    with (ROOT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(name, fields, rows):
    with (ROOT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


products = {row["sku"]: row for row in read("fashion_products_realistic_v2.csv")}
sales = {(row["sku"], row["sale_date"]): row for row in read("fashion_daily_sales_realistic_v2.csv")}
assert len(products) == 30 and len(sales) == 1800

flows = []
for sku, product in sorted(products.items()):
    sold_total = sum(int(sales[(sku, (START + timedelta(days=i)).isoformat())]["units_sold"]) for i in range(60))
    # An example replenishment for summer stock only; other groups have no
    # in-period receipts. Future inbound units in the product file are excluded.
    receipt = sold_total // 5 if sku.startswith("FSH-SS-") else 0
    opening = int(product["stock_on_hand"]) + sold_total - receipt
    running = opening
    for i in range(60):
        day = START + timedelta(days=i)
        units = int(sales[(sku, day.isoformat())]["units_sold"])
        inbound = receipt if i == 20 else 0
        ending = running + inbound - units
        assert ending >= 0, (sku, day)
        flows.append({"sku": sku, "date": day.isoformat(), "opening_stock": running,
                      "receipts": inbound, "customer_returns": 0, "supplier_returns": 0,
                      "writeoffs": 0, "adjustments": 0, "sold_units": units,
                      "closing_stock": ending})
        running = ending
    assert running == int(product["stock_on_hand"]), sku

write("fashion_stock_flow_2026.csv", ["sku", "date", "opening_stock", "receipts", "customer_returns",
     "supplier_returns", "writeoffs", "adjustments", "sold_units", "closing_stock"], flows)

references = []
for index, sku in enumerate(sorted(s for s in products if s.startswith("FSH-FW-")), 1):
    product = products[sku]
    first_order = 75 + index * 7
    later_receipts = 20 + (index % 4) * 8
    sold = 45 + (index * 19) % 85
    customer_returns = index % 4
    supplier_returns = index % 3
    writeoffs = index % 2
    available = first_order + later_receipts + customer_returns
    end_stock = available - sold - supplier_returns - writeoffs
    assert end_stock >= 0
    price = int(float(product["unit_price"]))
    cost = int(float(product["unit_cost"]))
    # Discounted past price is explicit. The revenue is a constructed amount.
    past_price = round(price * (0.78 + (index % 3) * 0.04))
    references.append({"current_sku": sku, "reference_name": f"2025FW 비교 상품 {index:02d}",
                       "season": "2025FW", "first_order": first_order,
                       "later_receipts": later_receipts, "customer_returns": customer_returns,
                       "supplier_returns": supplier_returns, "writeoffs": writeoffs,
                       "sold_units": sold, "end_stock": end_stock,
                       "sales_revenue": sold * past_price,
                       "gross_profit": sold * (past_price - cost)})

write("fashion_prior_fw_reference.csv", ["current_sku", "reference_name", "season", "first_order",
     "later_receipts", "customer_returns", "supplier_returns", "writeoffs", "sold_units",
     "end_stock", "sales_revenue", "gross_profit"], references)

print(f"Created {len(flows)} daily stock rows and {len(references)} prior-season comparable rows.")
