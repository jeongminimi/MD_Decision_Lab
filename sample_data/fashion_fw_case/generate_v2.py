import csv
from datetime import date, timedelta
import random

# Fix random seed for reproducibility
random.seed(20260831)

BASE_DIR = r"C:\Users\samsung\Documents\Codex\2026-10-24\x20\MD_Decision_Lab\sample_data\fashion_fw_case"

# 1. Load Original Products & Context
orig_products = []
with open(f"{BASE_DIR}\\fashion_products_20260831.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        orig_products.append(row)

orig_context = []
with open(f"{BASE_DIR}\\fashion_merchandising_context.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        orig_context.append(row)

# 2. Date Setup: 2026-07-03 to 2026-08-31 (60 days)
start_date = date(2026, 7, 3)
end_date = date(2026, 8, 31)
days_count = (end_date - start_date).days + 1 # 60 days
dates = [start_date + timedelta(days=i) for i in range(days_count)]

# 3. Simulate Realistic Daily Sales for each SKU
# We will define detailed realistic sales behaviors for each SKU:
sales_rows = []
stock_ledger = {} # To calculate beginning inventory and receipts

# Let's inspect each SKU category
for p in orig_products:
    sku = p["sku"]
    name = p["name"]
    category = p["category"]
    current_price = float(p["unit_price"])
    cost = float(p["unit_cost"])
    soh = int(p["stock_on_hand"])
    
    sku_sales_units = 0
    
    # We will simulate sales for 60 days
    sku_daily = []
    
    if sku.startswith("FSH-FW-"):
        # Fall new arrivals: Launch is 2026-09-01. 0 sales for all 60 days.
        for d in dates:
            sku_daily.append({
                "sku": sku,
                "sale_date": d.isoformat(),
                "units_sold": 0,
                "revenue": 0.0,
                "gross_margin": 0.0
            })
        # Beginning inventory and receipts for FW:
        # Received during August in preparation for Sept 1 launch
        receipts_in_period = soh
        beginning_stock = 0
        stock_ledger[sku] = {
            "beginning": beginning_stock,
            "receipts": receipts_in_period,
            "sales": 0,
            "ending": soh
        }

    elif sku.startswith("FSH-SS-"):
        # Summer items:
        # July had higher sales, especially weekends.
        # Promotion: July 18~19 (Weekend summer promo, 10% coupon applied)
        # August had slowing demand.
        # Late August: very low or 0 sales.
        
        # Characteristic profiles
        if sku == "FSH-SS-001": # Linen shirt: bestseller, but overstock
            # July: 2~5/day (weekends 4~7), Aug 1~15: 1~3/day, Aug 16~31: 0~2/day
            for d in dates:
                weekday = d.weekday() # 5=Sat, 6=Sun
                d_idx = (d - start_date).days
                
                # Base price: July was full price 55,000, Aug 1 onward marked down to current 49,000
                applied_price = 55000.0 if d < date(2026, 8, 1) else 49000.0
                
                # Special promo: July 18-19 weekend discount to 48,000
                if d in [date(2026, 7, 18), date(2026, 7, 19)]:
                    applied_price = 48000.0
                
                if d_idx <= 28: # July
                    units = random.choice([3, 4, 3, 5, 2]) if weekday in [5, 6] else random.choice([2, 3, 2, 4, 1])
                    if d in [date(2026, 7, 18), date(2026, 7, 19)]:
                        units += 3
                elif d_idx <= 43: # Early Aug
                    units = random.choice([2, 2, 3, 1]) if weekday in [5, 6] else random.choice([1, 2, 1, 0])
                else: # Late Aug
                    units = random.choice([1, 1, 2]) if weekday in [5, 6] else random.choice([0, 1, 0, 1, 0])
                    
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-SS-002": # Basic Tee: bulk order on July 24
            for d in dates:
                weekday = d.weekday()
                d_idx = (d - start_date).days
                applied_price = 32000.0 if d < date(2026, 8, 1) else 29000.0
                if d == date(2026, 7, 24):
                    # Corporate / club bulk order of 15 units!
                    units = 15
                    applied_price = 28000.0 # B2B bulk discount
                elif d_idx <= 28:
                    units = random.choice([3, 5, 4, 6]) if weekday in [5, 6] else random.choice([2, 3, 2, 4])
                elif d_idx <= 43:
                    units = random.choice([2, 3, 2]) if weekday in [5, 6] else random.choice([1, 2, 0, 1])
                else:
                    units = random.choice([1, 2, 1]) if weekday in [5, 6] else random.choice([0, 1, 0, 1])
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-SS-003": # Seersucker shorts: sharp weather dependency
            for d in dates:
                weekday = d.weekday()
                d_idx = (d - start_date).days
                applied_price = 45000.0 if d < date(2026, 8, 1) else 39000.0
                if d_idx <= 28:
                    units = random.choice([2, 4, 3]) if weekday in [5, 6] else random.choice([1, 2, 2, 0])
                elif d_idx <= 43:
                    units = random.choice([1, 2, 0]) if weekday in [5, 6] else random.choice([0, 1, 0])
                else:
                    # After mid August, demand crashed
                    units = random.choice([0, 1, 0]) if weekday in [5, 6] else 0
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-SS-009": # Windbreaker: Includes Below-Cost clearance on Aug 30-31!
            for d in dates:
                weekday = d.weekday()
                d_idx = (d - start_date).days
                applied_price = 69000.0 if d < date(2026, 8, 1) else 59000.0
                units = 0
                if d in [date(2026, 8, 30), date(2026, 8, 31)]:
                    # Flash clearance below cost! (Cost is 24,000, clearance sale at 21,000)
                    units = 3 if d == date(2026, 8, 30) else 2
                    applied_price = 21000.0 # Negative margin: 21,000 - 24,000 = -3,000/unit
                elif d_idx <= 28:
                    units = random.choice([2, 3, 2, 4]) if weekday in [5, 6] else random.choice([1, 2, 1, 0])
                elif d_idx <= 43:
                    units = random.choice([1, 2, 1]) if weekday in [5, 6] else random.choice([0, 1, 0])
                else:
                    units = random.choice([0, 1, 0])
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        else: # Other SS items (004, 005, 006, 007, 008, 010)
            for d in dates:
                weekday = d.weekday()
                d_idx = (d - start_date).days
                # July price was slightly higher (regular price)
                applied_price = round(current_price * 1.15 / 1000) * 1000 if d < date(2026, 8, 1) else current_price
                if sku in ["FSH-SS-005", "FSH-SS-007"]: # Overstock items
                    if d_idx <= 28:
                        units = random.choice([2, 3, 4, 2]) if weekday in [5, 6] else random.choice([1, 2, 2, 1])
                    elif d_idx <= 43:
                        units = random.choice([1, 2, 1]) if weekday in [5, 6] else random.choice([1, 0, 1])
                    else:
                        units = random.choice([1, 1, 0]) if weekday in [5, 6] else random.choice([0, 1, 0])
                else: # Moderate clearance items (004, 006, 008, 010)
                    if d_idx <= 28:
                        units = random.choice([1, 2, 2, 1]) if weekday in [5, 6] else random.choice([1, 1, 0, 1])
                    elif d_idx <= 43:
                        units = random.choice([1, 1, 0]) if weekday in [5, 6] else random.choice([0, 1, 0])
                    else:
                        units = random.choice([0, 1, 0]) if weekday in [5, 6] else random.choice([0, 0, 1, 0])
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        # Calculate inventory balance
        tot_sold = sum(x["units_sold"] for x in sku_daily)
        # To satisfy: Beginning + Receipts - Sales = SOH
        # For summer items, suppose beginning stock was large and some had mid-July reorder receipts
        if sku in ["FSH-SS-001", "FSH-SS-002"]:
            receipts = 50 # Early July reorder arrival
            beginning = soh + tot_sold - receipts
        else:
            receipts = 0
            beginning = soh + tot_sold
        stock_ledger[sku] = {
            "beginning": beginning,
            "receipts": receipts,
            "sales": tot_sold,
            "ending": soh
        }

    elif sku.startswith("FSH-EV-"):
        # Winter event items:
        # Event starts 2026-08-25 (7 days of event: Aug 25~31)
        # Prior to Aug 25: 0 sales (except Aug 22 VIP preview for 1 SKU)
        # Aug 25-31: Varied reaction across products!
        
        if sku == "FSH-EV-001": # Goose down long padding: explosive reaction!
            for d in dates:
                if d < date(2026, 8, 25):
                    units = 0
                    applied_price = 149000.0 # pre-event list price
                elif d == date(2026, 8, 25): # Launch Day Rush!
                    units = 9
                    applied_price = current_price # 119,000
                elif d.weekday() in [5, 6]: # Weekend rush
                    units = random.choice([5, 6, 7])
                    applied_price = current_price
                else: # Weekday
                    units = random.choice([4, 5, 4])
                    applied_price = current_price
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-EV-002": # Short padding: strong reaction
            for d in dates:
                if d < date(2026, 8, 25):
                    units = 0
                    applied_price = 99000.0
                elif d == date(2026, 8, 25):
                    units = 7
                    applied_price = current_price # 79,000
                elif d.weekday() in [5, 6]:
                    units = random.choice([4, 5])
                    applied_price = current_price
                else:
                    units = random.choice([3, 4, 3])
                    applied_price = current_price
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-EV-003": # Handmade wool coat: High ticket, steady 1~3 sales
            for d in dates:
                if d < date(2026, 8, 25):
                    units = 0
                    applied_price = 149000.0
                elif d == date(2026, 8, 25):
                    units = 4
                    applied_price = current_price # 109,000
                else:
                    units = random.choice([1, 2, 3, 2])
                    applied_price = current_price
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-EV-004": # Shearling jacket: Low reaction / poor fit for off-season
            for d in dates:
                if d < date(2026, 8, 25):
                    units = 0
                    applied_price = 129000.0
                else:
                    # Only 0~1 per day even after event!
                    units = random.choice([0, 1, 0, 1, 1, 0, 1])
                    applied_price = current_price # 95,000
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-EV-007": # Fleece slacks: Opening flash deal below cost!
            # Cost is 17,000, current price is 35,000.
            # On Aug 25 opening day: 6 units sold at 15,000 (below cost flash special!), remaining days at 35,000.
            for d in dates:
                if d < date(2026, 8, 25):
                    units = 0
                    applied_price = 49000.0
                elif d == date(2026, 8, 25):
                    units = 6
                    applied_price = 15000.0 # Below cost opening gimmick! (Cost 17,000 -> -2,000/unit)
                elif d.weekday() in [5, 6]:
                    units = random.choice([4, 5])
                    applied_price = current_price
                else:
                    units = random.choice([3, 4, 3])
                    applied_price = current_price
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        elif sku == "FSH-EV-008": # Corduroy pants: Had 1 VIP pre-sale on Aug 22
            for d in dates:
                if d == date(2026, 8, 22): # Pre-open VIP order
                    units = 2
                    applied_price = current_price
                elif d < date(2026, 8, 25):
                    units = 0
                    applied_price = 45000.0
                else:
                    units = random.choice([2, 3, 2, 4])
                    applied_price = current_price
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        else: # EV-005, EV-006 (Knitwear)
            for d in dates:
                if d < date(2026, 8, 25):
                    units = 0
                    applied_price = current_price * 1.3
                else:
                    units = random.choice([3, 4, 5, 3]) if d.weekday() in [5, 6] else random.choice([2, 3, 4, 3])
                    applied_price = current_price
                rev = round(units * applied_price, 2)
                gm = round(rev - units * cost, 2)
                sku_daily.append({"sku": sku, "sale_date": d.isoformat(), "units_sold": units, "revenue": rev, "gross_margin": gm})

        # Inventory balance for winter:
        # Reorderable = False -> Receipts in period = 0!
        # Beginning stock in warehouse = Ending (SOH) + Total sales in 60d
        tot_sold = sum(x["units_sold"] for x in sku_daily)
        stock_ledger[sku] = {
            "beginning": soh + tot_sold,
            "receipts": 0,
            "sales": tot_sold,
            "ending": soh
        }

    sales_rows.extend(sku_daily)

# Write CSV 1: fashion_products_realistic_v2.csv
prod_v2_path = f"{BASE_DIR}\\fashion_products_realistic_v2.csv"
prod_fields = ["sku", "name", "category", "stock_on_hand", "inbound_units", "lead_time_days", "target_cover_days", "unit_price", "unit_cost"]
with open(prod_v2_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=prod_fields)
    writer.writeheader()
    for p in orig_products:
        writer.writerow({k: p[k] for k in prod_fields})

# Write CSV 2: fashion_daily_sales_realistic_v2.csv
sales_v2_path = f"{BASE_DIR}\\fashion_daily_sales_realistic_v2.csv"
sales_fields = ["sku", "sale_date", "units_sold", "revenue", "gross_margin"]
with open(sales_v2_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=sales_fields)
    writer.writeheader()
    for r in sales_rows:
        writer.writerow(r)

print(f"Generated {len(orig_products)} products -> {prod_v2_path}")
print(f"Generated {len(sales_rows)} sales records -> {sales_v2_path}")
