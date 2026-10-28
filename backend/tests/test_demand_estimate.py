import unittest
from datetime import date

from app.services.demand_estimate import error_summary, estimate, seasonal_factor, windows


class DemandEstimateTests(unittest.TestCase):
    def test_windows_use_last_year_for_the_factor(self):
        span = windows(date(2020, 8, 31), 22)
        self.assertEqual(span["recent"], (date(2020, 8, 18), date(2020, 8, 31)))
        self.assertEqual(span["after"], (date(2020, 9, 1), date(2020, 9, 22)))
        self.assertEqual(span["base_last_year"], (date(2019, 8, 18), date(2019, 8, 31)))
        self.assertEqual(span["after_last_year"], (date(2019, 9, 1), date(2019, 9, 22)))

    def test_factor_and_estimates(self):
        # Last year 140 units in 14 days (10/day) then 176 in 22 days (8/day): factor 0.8.
        factor = seasonal_factor(140, 176, 22)
        self.assertEqual(factor, 0.8)
        self.assertEqual(estimate(28, 22, factor), {"velocity": 44.0, "seasonal": 35.2})
        self.assertIsNone(seasonal_factor(99, 50, 22))
        self.assertIsNone(estimate(28, 22, None)["seasonal"])

    def test_error_summary(self):
        result = error_summary([(12, 10), (6, 10)])
        self.assertEqual((result["wape_pct"], result["bias_pct"]), (30.0, -10.0))
        self.assertIsNone(error_summary([(5, 0)])["wape_pct"])


if __name__ == "__main__":
    unittest.main()
