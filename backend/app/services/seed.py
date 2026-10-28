from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DailySale, Product


DEMO_PRODUCTS = [
    {"sku": "MD-001", "name": "클래식 울 코트", "category": "아우터", "stock_on_hand": 12, "inbound_units": 0, "lead_time_days": 14, "target_cover_days": 45, "unit_price": 189000, "unit_cost": 82000, "daily": 1.2},
    {"sku": "MD-002", "name": "시그니처 니트 가디건", "category": "니트", "stock_on_hand": 180, "inbound_units": 40, "lead_time_days": 10, "target_cover_days": 45, "unit_price": 89000, "unit_cost": 36000, "daily": 2.0},
    {"sku": "MD-003", "name": "코튼 스트레이트 팬츠", "category": "하의", "stock_on_hand": 64, "inbound_units": 20, "lead_time_days": 9, "target_cover_days": 40, "unit_price": 79000, "unit_cost": 31000, "daily": 2.1},
    {"sku": "MD-004", "name": "라이트 패딩 베스트", "category": "아우터", "stock_on_hand": 0, "inbound_units": 30, "lead_time_days": 12, "target_cover_days": 35, "unit_price": 119000, "unit_cost": 51000, "daily": 1.4},
    {"sku": "MD-005", "name": "캐시미어 블렌드 머플러", "category": "잡화", "stock_on_hand": 95, "inbound_units": 0, "lead_time_days": 8, "target_cover_days": 40, "unit_price": 49000, "unit_cost": 18000, "daily": 0.7},
    {"sku": "MD-006", "name": "데일리 셔츠 블라우스", "category": "상의", "stock_on_hand": 38, "inbound_units": 12, "lead_time_days": 7, "target_cover_days": 35, "unit_price": 69000, "unit_cost": 27000, "daily": 1.1},
    {"sku": "MD-007", "name": "플리츠 롱 스커트", "category": "하의", "stock_on_hand": 22, "inbound_units": 0, "lead_time_days": 10, "target_cover_days": 35, "unit_price": 85000, "unit_cost": 34000, "daily": 0.5},
    {"sku": "MD-008", "name": "리브드 터틀넥 탑", "category": "상의", "stock_on_hand": 45, "inbound_units": 0, "lead_time_days": 7, "target_cover_days": 30, "unit_price": 59000, "unit_cost": 23000, "daily": 0.0},
]


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Product.id).limit(1)) is not None:
        return
    today = date.today()
    for item in DEMO_PRODUCTS:
        product = Product(**{key: value for key, value in item.items() if key != "daily"})
        db.add(product)
        db.flush()
        daily = item["daily"]
        if daily <= 0:
            continue
        for offset in range(30):
            units = max(0, round(daily + ((offset % 5) - 2) * daily * 0.15))
            if units == 0 and offset % 3:
                continue
            revenue = units * item["unit_price"]
            db.add(DailySale(
                product_id=product.id,
                sale_date=today - timedelta(days=29 - offset),
                units_sold=units,
                revenue=revenue,
                gross_margin=units * (item["unit_price"] - item["unit_cost"]),
            ))
    db.commit()
