import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DailySale, Product
from app.services.analysis import analyze_product


AS_OF = date(2018, 8, 31)


class DemandDecisionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.product = Product(
            sku="TEST-1", name="Test product", category="test", stock_on_hand=10,
            inbound_units=0, lead_time_days=7, target_cover_days=30,
            unit_price=20, unit_cost=10,
        )
        self.db.add(self.product)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def sales(self, offset_days, units):
        self.db.add(DailySale(
            product_id=self.product.id, sale_date=AS_OF - timedelta(days=offset_days),
            units_sold=units, revenue=units * 20,
        ))
        self.db.flush()

    def test_recent_surge_changes_coverage_and_replenishment(self):
        for offset in range(7):
            self.sales(offset, 3)
        for offset in range(7, 30):
            self.sales(offset, 1)
        result = analyze_product(self.product, self.db, AS_OF)
        self.assertEqual((result.units_7d, result.units_30d), (21, 44))
        self.assertEqual(result.demand_basis, "7d")
        self.assertEqual(result.days_of_cover, 3.3)
        self.assertEqual(result.suggested_replenishment_units, 80)

    def test_small_sample_uses_30_day_rate_with_warning(self):
        self.sales(0, 2)
        result = analyze_product(self.product, self.db, AS_OF)
        self.assertEqual(result.demand_basis, "30d")
        self.assertTrue(any("10개 미만" in warning for warning in result.data_warnings))
        self.assertTrue(any("3일 미만" in warning for warning in result.data_warnings))

    def test_no_recent_sales_suppresses_replenishment(self):
        for offset in range(7, 17):
            self.sales(offset, 2)
        result = analyze_product(self.product, self.db, AS_OF)
        self.assertEqual(result.risk, "data_insufficient")
        self.assertIsNone(result.suggested_replenishment_units)
        self.assertTrue(any("최근 7일 판매가 크게 줄었지만" in warning for warning in result.data_warnings))

    def test_small_recent_sample_after_drop_suppresses_replenishment(self):
        for offset in range(7, 20):
            self.sales(offset, 2)
        self.sales(0, 2)
        result = analyze_product(self.product, self.db, AS_OF)
        self.assertEqual(result.risk, "data_insufficient")
        self.assertEqual(result.demand_basis, "30d")
        self.assertIsNone(result.suggested_replenishment_units)


if __name__ == "__main__":
    unittest.main()
