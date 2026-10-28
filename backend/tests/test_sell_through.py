import unittest

from app.services.sell_through import sell_through


class SellThroughTests(unittest.TestCase):
    def test_closed_ledger_gives_a_ratio(self):
        result = sell_through(opening=80, received=20, sold=60, closing=40)
        self.assertEqual((result["status"], result["pct"]), ("ok", 60.0))

    def test_unrecorded_movement_withholds_the_ratio(self):
        result = sell_through(opening=80, received=20, sold=60, closing=35)
        self.assertEqual((result["status"], result["pct"], result["difference_units"]), ("mismatch", None, -5))
        self.assertIn("-5", result["reason"])

    def test_missing_inputs_and_empty_supply(self):
        self.assertEqual(sell_through(opening=None, received=0, sold=3, closing=0)["status"], "missing")
        self.assertEqual(sell_through(opening=0, received=0, sold=0, closing=0)["status"], "no_supply")


if __name__ == "__main__":
    unittest.main()
