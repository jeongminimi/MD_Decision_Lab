import unittest
from datetime import date

from app.services.stock_timeline import check_daily_availability

AS_OF = date(2026, 9, 1)


class StockTimelineTests(unittest.TestCase):
    def test_late_receipt_cannot_hide_an_earlier_gap(self):
        # 30-day total fits (10 + 100 >= 100), but stock runs out on day 4 before the day-25 receipt.
        result = check_daily_availability(AS_OF, 10, [(date(2026, 9, 26), 100)], 100)
        self.assertFalse(result["feasible"])
        self.assertEqual(result["first_gap_date"], date(2026, 9, 5))
        self.assertEqual(result["available_units"], 110)
        self.assertEqual(result["max_gap_units"], 70)  # day 24: demand 80 vs supply 10

    def test_early_receipt_is_feasible(self):
        result = check_daily_availability(AS_OF, 10, [(date(2026, 9, 3), 100)], 100)
        self.assertTrue(result["feasible"])
        self.assertIsNone(result["first_gap_date"])
        self.assertEqual(result["max_gap_units"], 0)

    def test_exact_boundary_is_not_a_gap(self):
        # 30 units over 30 days with 30 on hand: cumulative demand never exceeds supply.
        self.assertTrue(check_daily_availability(AS_OF, 30, [], 30)["feasible"])
        self.assertFalse(check_daily_availability(AS_OF, 29, [], 30)["feasible"])

    def test_receipts_after_the_horizon_are_not_counted(self):
        result = check_daily_availability(AS_OF, 50, [(date(2026, 10, 2), 500)], 40)
        self.assertTrue(result["feasible"])
        self.assertEqual(result["available_units"], 50)
        self.assertEqual(result["receipts_counted"], [])


if __name__ == "__main__":
    unittest.main()
