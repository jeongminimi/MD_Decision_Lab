import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DailySale, MDAction, Product
from app.services.action_outcome import evaluate_action


class ActionOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        product = Product(
            sku="OUTCOME-1", name="Test", category="test", stock_on_hand=8,
            inbound_units=0, lead_time_days=7, target_cover_days=30,
            unit_price=100, unit_cost=60,
        )
        self.db.add(product)
        self.db.flush()
        self.action = MDAction(
            product_id=product.id, action_type="promotion", note="test", status="completed",
            stock_before=12, units_30d_before=20, revenue_30d_before=2000,
            completed_at=datetime(2026, 10, 10, 12),
        )
        self.db.add(self.action)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def sales(self, day, units):
        self.db.add(DailySale(
            product_id=self.action.product_id, sale_date=day, units_sold=units,
            revenue=units * 100, gross_margin=units * 40,
        ))
        self.db.flush()

    def test_requires_explicit_zero_sale_days(self):
        completed = date(2026, 10, 10)
        for offset in range(1, 8):
            self.sales(completed - timedelta(days=offset), 1)
        for offset in range(1, 7):
            self.sales(completed + timedelta(days=offset), 2)
        result = evaluate_action(self.action, self.db, date(2026, 10, 27))
        self.assertEqual(result["status"], "waiting_for_data")
        self.assertEqual(result["missing_after_days"], 1)
        self.assertIsNone(result["before"])

    def test_complete_equal_windows_are_descriptive_only(self):
        completed = date(2026, 10, 10)
        for offset in range(1, 8):
            self.sales(completed - timedelta(days=offset), 1)
            self.sales(completed + timedelta(days=offset), 2)
        result = evaluate_action(self.action, self.db, date(2026, 10, 27))
        self.assertEqual(result["status"], "comparable")
        self.assertEqual((result["before"]["units"], result["after"]["units"]), (7, 14))
        self.assertEqual((result["before"]["gross_margin"], result["after"]["gross_margin"]), (280, 560))
        self.assertIn("인과 효과가 아닙니다", result["interpretation"])

    def test_completion_date_uses_korean_calendar_day(self):
        self.action.completed_at = datetime(2026, 10, 10, 23, 30)  # stored UTC
        result = evaluate_action(self.action, self.db, date(2026, 10, 27))
        self.assertEqual(result["action_date"], date(2026, 10, 11))
        self.assertEqual(result["after_period"]["start"], date(2026, 10, 12))


if __name__ == "__main__":
    unittest.main()
