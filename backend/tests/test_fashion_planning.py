import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.fashion_routes import import_sample
from app.api.fashion_planning_routes import PlanDecisionInput, import_planning_sample, list_plan_decisions, planning_analysis, planning_status, save_plan_decision
from app.database import Base
from app.models import DailySale, FashionPriorReference, FashionSeasonPlanDecision, FashionStockFlow, Product


class FashionPlanningTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        import_sample(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_stock_flow_is_reconciled_without_replacing_sales(self):
        before = self.db.scalar(select(func.count(DailySale.id)))
        imported = import_planning_sample(self.db)
        self.assertEqual((imported["flow_rows"], imported["reference_rows"]), (1800, 12))
        self.assertEqual(self.db.scalar(select(func.count(DailySale.id))), before)
        self.assertEqual(self.db.scalar(select(func.count(FashionStockFlow.id))), 1800)
        self.assertEqual(self.db.scalar(select(func.count(FashionPriorReference.product_id))), 12)
        self.assertTrue(planning_status(self.db)["ready"])
        result = planning_analysis(0, 85, self.db)
        self.assertEqual(len(result["flow_summary"]), 30)
        self.assertTrue(all(item["reconciled_with_current_inputs"] for item in result["flow_summary"]))
        self.assertEqual(len(result["plans"]), 12)
        self.assertTrue(all(item["projected_end_stock"] >= 0 for item in result["plans"]))

    def test_sensitivity_and_existing_data_are_preserved(self):
        import_planning_sample(self.db)
        low = planning_analysis(-30, 85, self.db)
        high = planning_analysis(50, 85, self.db)
        low_plan = next(p for p in low["plans"] if p["sku"] == "FSH-FW-012")
        high_plan = next(p for p in high["plans"] if p["sku"] == "FSH-FW-012")
        self.assertGreater(high_plan["assumed_demand"], low_plan["assumed_demand"])
        self.assertGreaterEqual(high_plan["additional_order_to_review"], low_plan["additional_order_to_review"])
        with self.assertRaises(HTTPException) as error:
            import_planning_sample(self.db)
        self.assertEqual(error.exception.status_code, 409)
        product = self.db.scalar(select(Product).where(Product.sku == "FSH-FW-001"))
        product.stock_on_hand += 1
        self.db.commit()
        changed = planning_analysis(0, 85, self.db)
        row = next(item for item in changed["flow_summary"] if item["sku"] == product.sku)
        self.assertFalse(row["reconciled_with_current_inputs"])

    def test_plan_decision_saves_server_calculation_and_reason_only(self):
        import_planning_sample(self.db)
        before = self.db.scalar(select(func.count(DailySale.id)))
        payload = PlanDecisionInput(sku="FSH-FW-012", growth_pct=15,
                                    target_sell_through_pct=90, rationale="예약 주문 확인 후 추가 발주 검토")
        result = save_plan_decision(payload, self.db)
        self.assertTrue(result["saved"])
        stored = self.db.scalar(select(FashionSeasonPlanDecision))
        expected = next(item for item in planning_analysis(15, 90, self.db)["plans"]
                        if item["sku"] == payload.sku)
        self.assertEqual(stored.assumed_demand, expected["assumed_demand"])
        self.assertEqual(stored.additional_order_to_review, expected["additional_order_to_review"])
        self.assertEqual(self.db.scalar(select(func.count(DailySale.id))), before)
        self.assertEqual(len(list_plan_decisions(self.db)), 1)
        with self.assertRaises(HTTPException) as error:
            save_plan_decision(PlanDecisionInput(sku="FSH-FW-012", growth_pct=0,
                               target_sell_through_pct=85, rationale="     "), self.db)
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
