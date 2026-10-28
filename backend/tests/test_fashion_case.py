import unittest
import asyncio
import io

from fastapi import HTTPException
from fastapi import UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.fashion_routes import CASE_DATE, DecisionInput, ProductInput, ScenarioComparisonInput, ScenarioOptionInput, analysis, compare_options, create_decision, import_sample, import_sales_corrections, list_decisions, markdown_check, status, update_product_inputs
from app.database import Base
from app.models import DailySale, Product


class FashionCaseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_sample_import_and_distinct_lifecycle_decisions(self):
        result = import_sample(self.db)
        self.assertEqual((result["product_count"], result["sale_rows"]), (30, 1800))
        self.assertTrue(status(self.db)["imported"])
        self.assertEqual(self.db.scalar(select(func.count(DailySale.id))), 1800)
        items = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}
        self.assertEqual(items["FSH-SS-001"]["risk"], "overstock_risk")
        self.assertEqual(items["FSH-SS-001"]["gross_margin_rate_30d_pct"], 63.3)
        self.assertEqual(items["FSH-SS-001"]["unit_markup_pct"], 172.2)
        self.assertEqual(items["FSH-FW-001"]["recommendation"], "출시 준비 상태 확인")
        self.assertEqual(items["FSH-EV-001"]["risk"], "stockout_risk")
        self.assertIsNone(items["FSH-EV-001"]["suggested_replenishment_units"])
        self.assertIn("재발주가 불가능", items["FSH-EV-001"]["recommendation_reason"])
        self.assertEqual(items["FSH-EV-001"]["units_7d"], 32)

    def test_repeat_import_preserves_existing_products(self):
        import_sample(self.db)
        before = self.db.scalar(select(func.count(Product.id)))
        with self.assertRaises(HTTPException) as error:
            import_sample(self.db)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count(Product.id))), before)

    def test_markdown_shows_required_units_without_claiming_sales_lift(self):
        import_sample(self.db)
        result = markdown_check("FSH-SS-001", 20, self.db)
        self.assertGreater(result["break_even_units_30d"], result["baseline_units_30d"])
        self.assertIn("예측하거나", result["note"])

    def test_two_options_compare_gross_profit_without_changing_observed_sales(self):
        import_sample(self.db)
        before = self.db.scalar(select(func.count(DailySale.id)))
        product = self.db.scalar(select(Product).where(Product.sku == "FSH-SS-001"))
        response = compare_options(ScenarioComparisonInput(
            sku=product.sku,
            options=[
                ScenarioOptionInput(label="가격 유지", discount_pct=0, expected_units_30d=20, purchase_units=0),
                ScenarioOptionInput(label="할인", discount_pct=20, expected_units_30d=35, purchase_units=0),
            ],
        ), self.db)
        a, b = response["options"]
        self.assertEqual(a["unit_price"], product.unit_price)
        self.assertEqual(b["unit_price"], round(product.unit_price * 0.8, 2))
        self.assertEqual(a["estimated_gross_profit"], round(20 * (product.unit_price - product.unit_cost), 2))
        self.assertEqual(b["estimated_gross_profit"], round(35 * (product.unit_price * 0.8 - product.unit_cost), 2))
        observed_item = next(item for item in analysis(CASE_DATE, self.db)["products"] if item["sku"] == product.sku)
        self.assertEqual(response["observed"]["units_30d"], observed_item["units_30d"])
        self.assertEqual(self.db.scalar(select(func.count(DailySale.id))), before)
        self.assertIn("가정", response["note"])

    def test_infeasible_units_do_not_produce_projected_profit(self):
        import_sample(self.db)
        result = compare_options(ScenarioComparisonInput(sku="FSH-SS-001", options=[
            ScenarioOptionInput(label="A", expected_units_30d=10000),
            ScenarioOptionInput(label="B", expected_units_30d=1),
        ]), self.db)
        self.assertFalse(result["options"][0]["feasible"])
        self.assertIsNone(result["options"][0]["estimated_gross_profit"])
        self.assertTrue(result["options"][1]["feasible"])

    def test_discontinued_product_cannot_assume_additional_purchase(self):
        import_sample(self.db)
        with self.assertRaises(HTTPException) as error:
            compare_options(ScenarioComparisonInput(sku="FSH-EV-001", options=[
                ScenarioOptionInput(label="재발주", expected_units_30d=20, purchase_units=10),
                ScenarioOptionInput(label="소진", expected_units_30d=20),
            ]), self.db)
        self.assertEqual(error.exception.status_code, 400)

    def test_md_decision_keeps_observed_snapshot(self):
        import_sample(self.db)
        saved = create_decision(DecisionInput(sku="FSH-EV-001", action_type="sellout_monitor",
            rationale="재발주가 불가능하여 소진 수량을 확인한다."), self.db)
        self.assertEqual(saved["observed_units_7d"], 32)
        self.assertEqual(saved["assumed_stock_on_hand"], 22)
        self.assertEqual(list_decisions(self.db)[0]["id"], saved["id"])

    def test_decision_with_comparison_option_saved_correctly(self):
        import_sample(self.db)
        saved_b = create_decision(DecisionInput(
            sku="FSH-SS-001",
            action_type="option_b",
            chosen_option="B",
            discount_pct=15.0,
            expected_units_30d=40,
            purchase_units=0,
            estimated_revenue=1666000.0,
            estimated_gross_profit=946000.0,
            estimated_remaining_stock=105,
            feasible=True,
            rationale="15% 할인으로 월 40장 소진을 목표로 진행한다."
        ), self.db)
        self.assertEqual(saved_b["chosen_option"], "B")
        self.assertEqual(saved_b["discount_pct"], 15.0)
        self.assertEqual(saved_b["expected_units_30d"], 40)
        self.assertEqual(saved_b["purchase_units"], 0)
        self.assertEqual(saved_b["estimated_revenue"], 1666000.0)
        self.assertEqual(saved_b["estimated_gross_profit"], 946000.0)
        self.assertEqual(saved_b["estimated_remaining_stock"], 105)
        self.assertTrue(saved_b["feasible"])

    def test_decision_infeasible_does_not_store_arbitrary_profit(self):
        import_sample(self.db)
        # FSH-SS-001 total available stock is 145. User inputs 500 units (shortage).
        saved = create_decision(DecisionInput(
            sku="FSH-SS-001",
            action_type="option_b",
            chosen_option="B",
            discount_pct=20.0,
            expected_units_30d=500,
            purchase_units=0,
            estimated_revenue=19600000.0, # client erroneously sends calculated revenue
            estimated_gross_profit=10600000.0, # client erroneously sends calculated profit
            estimated_remaining_stock=-355,
            feasible=True, # client erroneously claims feasible
            rationale="재고를 초과하는 가정이라도 이익은 저장되지 않아야 한다."
        ), self.db)
        self.assertFalse(saved["feasible"])
        self.assertIsNone(saved["estimated_gross_profit"])
        self.assertIsNone(saved["estimated_revenue"])
        self.assertIsNone(saved["estimated_remaining_stock"])

    def test_decision_recalculates_server_side_ignoring_client_manipulation(self):
        import_sample(self.db)
        # FSH-SS-001: unit_price=49000, unit_cost=18000, stock=145
        # discount 10% -> price=44100, margin_per_unit = 44100 - 18000 = 26100
        # expected_units=30 -> rev=1323000, profit=783000, remaining=115
        saved = create_decision(DecisionInput(
            sku="FSH-SS-001",
            action_type="option_b",
            chosen_option="B",
            discount_pct=10.0,
            expected_units_30d=30,
            purchase_units=0,
            estimated_revenue=99999999.0, # falsified client values
            estimated_gross_profit=88888888.0,
            estimated_remaining_stock=9999,
            feasible=False, # falsified
            rationale="서버가 직접 올바른 수식을 계산하여 저장하는지 검증한다."
        ), self.db)
        self.assertTrue(saved["feasible"])
        self.assertEqual(saved["estimated_revenue"], 1323000.0)
        self.assertEqual(saved["estimated_gross_profit"], 783000.0)
        self.assertEqual(saved["estimated_remaining_stock"], 115)

    def test_decision_rejects_purchase_for_discontinued_product(self):
        import_sample(self.db)
        # FSH-EV-001 is reorderable=False. Purchase units must be rejected with 400.
        with self.assertRaises(HTTPException) as ctx:
            create_decision(DecisionInput(
                sku="FSH-EV-001",
                action_type="option_b",
                chosen_option="B",
                discount_pct=10.0,
                expected_units_30d=20,
                purchase_units=15, # Illegal purchase for discontinued item
                rationale="재발주 불가 상품의 추가 매입 시도는 거부되어야 한다."
            ), self.db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("재발주가 불가능", ctx.exception.detail)

    def test_decision_hold_does_not_store_arbitrary_performance(self):
        import_sample(self.db)
        # FSH-FW-001 is reorderable=True. Test that hold wipes out any hypothetical metrics.
        saved = create_decision(DecisionInput(
            sku="FSH-FW-001",
            action_type="hold",
            chosen_option="hold",
            discount_pct=25.0, # Should be ignored and wiped to None
            expected_units_30d=50,
            purchase_units=10,
            estimated_revenue=5000000.0,
            estimated_gross_profit=2000000.0,
            rationale="추가 데이터를 확인하기 전까지 결정을 보류한다."
        ), self.db)
        self.assertEqual(saved["chosen_option"], "hold")
        self.assertIsNone(saved["discount_pct"])
        self.assertIsNone(saved["expected_units_30d"])
        self.assertEqual(saved["purchase_units"], 0)
        self.assertIsNone(saved["estimated_revenue"])
        self.assertIsNone(saved["estimated_gross_profit"])
        self.assertIsNone(saved["estimated_remaining_stock"])
        self.assertIsNone(saved["feasible"])

    def test_decision_contradictory_option_a_rejected(self):
        import_sample(self.db)
        with self.assertRaises(HTTPException) as ctx:
            create_decision(DecisionInput(
                sku="FSH-SS-001",
                action_type="option_a",
                chosen_option="A",
                discount_pct=15.0, # Option A must have 0% discount
                expected_units_30d=30,
                rationale="A안에 할인이 들어가면 모순이다."
            ), self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_decision_action_type_chosen_option_contradictions(self):
        import_sample(self.db)
        cases = [
            ("option_a", "B"),
            ("option_b", "A"),
            ("hold", "B"),
            ("hold", "A"),
            ("option_a", "hold"),
            ("option_b", "hold"),
            ("markdown_review", "A"),
            ("markdown_review", "B"),
            ("markdown_review", "hold"),
        ]
        for action, chosen in cases:
            with self.subTest(action=action, chosen=chosen):
                with self.assertRaises(HTTPException) as ctx:
                    create_decision(DecisionInput(
                        sku="FSH-SS-001",
                        action_type=action,
                        chosen_option=chosen,
                        rationale="모순된 조합은 400으로 거부되어야 합니다."
                    ), self.db)
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertIn("모순", ctx.exception.detail)

    def test_decision_missing_chosen_option_compatibility_policy(self):
        import_sample(self.db)
        # 1. option_a without chosen_option -> auto-resolves to 'A'
        res_a = create_decision(DecisionInput(
            sku="FSH-SS-001",
            action_type="option_a",
            chosen_option=None,
            rationale="누락 시 option_a는 A안으로 자동 보정"
        ), self.db)
        self.assertEqual(res_a["chosen_option"], "A")
        self.assertEqual(res_a["discount_pct"], 0.0)

        # 2. option_b without chosen_option -> auto-resolves to 'B'
        res_b = create_decision(DecisionInput(
            sku="FSH-SS-001",
            action_type="option_b",
            chosen_option=None,
            discount_pct=10.0,
            expected_units_30d=30,
            rationale="누락 시 option_b는 B안으로 자동 보정"
        ), self.db)
        self.assertEqual(res_b["chosen_option"], "B")
        self.assertEqual(res_b["discount_pct"], 10.0)

        # 3. hold without chosen_option -> auto-resolves to 'hold'
        res_hold = create_decision(DecisionInput(
            sku="FSH-FW-001",
            action_type="hold",
            chosen_option=None,
            rationale="누락 시 hold는 hold로 자동 보정"
        ), self.db)
        self.assertEqual(res_hold["chosen_option"], "hold")
        self.assertIsNone(res_hold["estimated_revenue"])

        # 4. legacy action without chosen_option -> resolves to None
        res_legacy = create_decision(DecisionInput(
            sku="FSH-SS-001",
            action_type="markdown_review",
            chosen_option=None,
            rationale="기존 레거시 액션은 chosen_option=None 유지"
        ), self.db)
        self.assertIsNone(res_legacy["chosen_option"])

    def test_recomputation_matches_comparison_screen_in_all_scenarios(self):
        import_sample(self.db)
        target_sku = "FSH-SS-001"

        # Scenario 1: Normal Option B (feasible)
        comp_res = compare_options(ScenarioComparisonInput(
            sku=target_sku,
            options=[
                ScenarioOptionInput(label="A", discount_pct=0, expected_units_30d=22, purchase_units=0),
                ScenarioOptionInput(label="B", discount_pct=15, expected_units_30d=35, purchase_units=0),
            ]
        ), self.db)
        opt_b_comp = comp_res["options"][1]

        save_res = create_decision(DecisionInput(
            sku=target_sku,
            action_type="option_b",
            chosen_option="B",
            discount_pct=15.0,
            expected_units_30d=35,
            purchase_units=0,
            rationale="비교 화면 수치와 저장 수치 정합성 검증"
        ), self.db)
        self.assertTrue(save_res["feasible"])
        self.assertEqual(save_res["estimated_revenue"], opt_b_comp["estimated_revenue"])
        self.assertEqual(save_res["estimated_gross_profit"], opt_b_comp["estimated_gross_profit"])
        self.assertEqual(save_res["estimated_remaining_stock"], opt_b_comp["estimated_remaining_stock"])

        # Scenario 2: Infeasible Option B (Stockout / Shortfall)
        # FSH-SS-001 stock=145, available=145. Request 200 units.
        comp_infeasible = compare_options(ScenarioComparisonInput(
            sku=target_sku,
            options=[
                ScenarioOptionInput(label="A", discount_pct=0, expected_units_30d=22, purchase_units=0),
                ScenarioOptionInput(label="B", discount_pct=10, expected_units_30d=200, purchase_units=0),
            ]
        ), self.db)
        opt_b_infeasible = comp_infeasible["options"][1]
        self.assertFalse(opt_b_infeasible["feasible"])
        self.assertIsNone(opt_b_infeasible["estimated_revenue"])
        self.assertIsNone(opt_b_infeasible["estimated_gross_profit"])

        save_infeasible = create_decision(DecisionInput(
            sku=target_sku,
            action_type="option_b",
            chosen_option="B",
            discount_pct=10.0,
            expected_units_30d=200,
            purchase_units=0,
            rationale="재고 부족 상황에서 임의 이익 수치가 저장되지 않아야 함"
        ), self.db)
        self.assertFalse(save_infeasible["feasible"])
        self.assertIsNone(save_infeasible["estimated_revenue"])
        self.assertIsNone(save_infeasible["estimated_gross_profit"])
        self.assertIsNone(save_infeasible["estimated_remaining_stock"])

    def test_current_price_edit_does_not_rewrite_historical_gross_margin(self):
        import_sample(self.db)
        original = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}["FSH-SS-001"]
        changed = update_product_inputs("FSH-SS-001", ProductInput(
            stock_on_hand=100, inbound_units=0, unit_price=59000, unit_cost=20000), self.db)
        self.assertEqual(changed.stock_on_hand, 100)
        self.assertEqual(changed.unit_markup_pct, 195.0)
        self.assertEqual(changed.gross_margin_30d, original["gross_margin_30d"])

    def test_sales_csv_correction_recalculates_period_margin(self):
        import_sample(self.db)
        before = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}["FSH-SS-001"]
        content = b"sku,sale_date,units_sold,revenue,gross_margin\nFSH-SS-001,2026-08-31,2,98000,62000\n"
        file = UploadFile(filename="correction.csv", file=io.BytesIO(content))
        result = asyncio.run(import_sales_corrections(file, self.db))
        after = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}["FSH-SS-001"]
        self.assertEqual(result["updated"], 1)
        self.assertNotEqual(after["gross_margin_30d"], before["gross_margin_30d"])

    def test_invalid_sales_csv_does_not_apply_earlier_rows(self):
        import_sample(self.db)
        before = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}["FSH-SS-001"]
        content = b"sku,sale_date,units_sold,revenue,gross_margin\nFSH-SS-001,2026-08-31,2,98000,62000\nFSH-SS-001,2026-08-30,1,49000,99000\n"
        file = UploadFile(filename="invalid.csv", file=io.BytesIO(content))
        with self.assertRaises(HTTPException):
            asyncio.run(import_sales_corrections(file, self.db))
        after = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}["FSH-SS-001"]
        self.assertEqual(after["gross_margin_30d"], before["gross_margin_30d"])

    def test_missing_margin_is_estimated_from_current_cost(self):
        import_sample(self.db)
        content = b"sku,sale_date,units_sold,revenue\nFSH-SS-001,2026-08-31,2,98000\n"
        file = UploadFile(filename="sales.csv", file=io.BytesIO(content))
        asyncio.run(import_sales_corrections(file, self.db))
        before = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}["FSH-SS-001"]
        self.assertTrue(before["margin_is_estimated"])
        self.assertIsNotNone(before["gross_margin_rate_30d_pct"])
        update_product_inputs("FSH-SS-001", ProductInput(stock_on_hand=145, inbound_units=0,
            unit_price=49000, unit_cost=20000), self.db)
        after = {item["sku"]: item for item in analysis(CASE_DATE, self.db)["products"]}["FSH-SS-001"]
        self.assertEqual(after["gross_margin_30d"], before["gross_margin_30d"] - 4000)


if __name__ == "__main__":
    unittest.main()
