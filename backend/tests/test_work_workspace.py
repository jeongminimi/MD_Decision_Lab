import asyncio
import io
import unittest
from datetime import date

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.api.work_routes import (
    WorkComparePayload, WorkDecisionPayload, WorkInputPayload, analysis, append_company_sales, compare,
    mark_executed, outcome, save_decision, update_inputs, upload_dataset,
    ExecutionPayload,
)
from app.database import Base
from app.models import WorkDataset, WorkDecision, WorkProductInput, WorkInputSnapshot


PRODUCTS = b"sku,name,category,stock_on_hand,inbound_units,lead_time_days,unit_price_krw,unit_cost_krw,reorderable\nA-1,Coat,Outer,10,0,7,80000,40000,false\n"
SALES = b"sku,sale_date,units_sold,revenue,gross_margin\nA-1,2026-09-01,1,80000,40000\nA-1,2026-09-02,2,160000,80000\n"


class WorkWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def upload(self, sales=SALES, products=PRODUCTS):
        return asyncio.run(upload_dataset(
            name="My apparel", snapshot_date=date(2026, 9, 2), complete_calendar=True,
            products_file=UploadFile(filename="products.csv", file=io.BytesIO(products)),
            sales_file=UploadFile(filename="sales.csv", file=io.BytesIO(sales)), db=self.db,
        ))

    def test_unknown_sale_sku_rejects_whole_upload(self):
        bad = SALES + b"MISSING,2026-09-02,1,10000,1000\n"
        with self.assertRaises(HTTPException):
            self.upload(bad)
        self.assertEqual(self.db.scalar(select(func.count(WorkDataset.id))), 0)

    def test_company_upload_preserves_observed_and_assumptions(self):
        created = self.upload()
        result = analysis(created["id"], date(2026, 9, 2), None, None, self.db)
        self.assertEqual(result["summary"]["units_30d"], 3)
        product = result["products"][0]
        self.assertEqual(product["stock_on_hand"], 10)
        self.assertEqual(product["observed_gross_profit_30d"], 120000)
        self.assertEqual(product["input_source"], "company_upload")
        self.assertEqual(product["risk"], "data_gap")

    def test_hm_without_inputs_never_shows_inventory_or_krw(self):
        created = self.upload()
        dataset = self.db.get(WorkDataset, created["id"])
        dataset.kind = "hm"
        self.db.execute(delete(WorkProductInput))
        self.db.execute(delete(WorkInputSnapshot))
        self.db.commit()
        result = analysis(created["id"], date(2026, 9, 2), None, None, self.db)
        product = result["products"][0]
        self.assertIsNone(product["observed_revenue_30d"])
        self.assertIsNone(product["observed_gross_profit_30d"])
        self.assertIsNone(product["input_source"])
        update_inputs(created["id"], "A-1", WorkInputPayload(as_of_date=date(2026, 9, 2)), self.db)
        result = analysis(created["id"], date(2026, 9, 2), None, None, self.db)
        self.assertIsNone(result["products"][0]["days_of_cover"])
        self.assertIsNone(result["products"][0]["stock_on_hand"])

    def test_server_comparison_rejects_discontinued_replenishment(self):
        created = self.upload()
        payload = WorkComparePayload(dataset_id=created["id"], sku="A-1", as_of_date=date(2026, 9, 2),
                                     discount_pct=10, expected_units_30d=4, purchase_units=2)
        with self.assertRaises(HTTPException) as error:
            compare(payload, self.db)
        self.assertEqual(error.exception.status_code, 400)
        payload.purchase_units = 0
        self.assertEqual(compare(payload, self.db)["estimated_gross_profit_krw"], 128000)

    def test_decision_is_not_execution_or_causal_outcome(self):
        created = self.upload()
        decision = save_decision(WorkDecisionPayload(
            dataset_id=created["id"], sku="A-1", as_of_date=date(2026, 9, 2),
            discount_pct=0, expected_units_30d=3, purchase_units=0,
            action="현재 유지", rationale="현재 수량으로 판매를 이어갑니다.",
        ), self.db)
        saved = self.db.get(WorkDecision, decision["id"])
        self.assertIsNone(saved.executed_at)
        self.assertEqual(outcome(saved.id, self.db)["status"], "not_executed")
        mark_executed(saved.id, ExecutionPayload(executed_at=date(2026, 9, 2)), self.db)
        self.assertEqual(outcome(saved.id, self.db)["status"], "waiting_for_data")

    def test_new_sales_enable_descriptive_outcome_only_after_full_window(self):
        initial = SALES.split(b"\n", 1)[0] + b"\nA-1,2026-08-31,1,80000,40000\n" + SALES.split(b"\n", 1)[1]
        created = self.upload(initial)
        saved = save_decision(WorkDecisionPayload(
            dataset_id=created["id"], sku="A-1", as_of_date=date(2026, 9, 2),
            discount_pct=0, expected_units_30d=3, purchase_units=0,
            action="프로모션 검토", rationale="기간별 판매량을 확인하고 조치를 기록합니다.",
        ), self.db)
        mark_executed(saved["id"], ExecutionPayload(executed_at=date(2026, 9, 7)), self.db)
        self.assertEqual(outcome(saved["id"], self.db)["status"], "waiting_for_data")
        extra = b"sku,sale_date,units_sold,revenue,gross_margin\n" + b"".join(
            f"A-1,2026-09-{day:02d},1,80000,40000\n".encode() for day in range(3, 14))
        result = asyncio.run(append_company_sales(created["id"], True,
            UploadFile(filename="next.csv", file=io.BytesIO(extra)), self.db))
        self.assertEqual(result["updated"], 11)
        observed = outcome(saved["id"], self.db)
        self.assertEqual(observed["status"], "descriptive")
        self.assertEqual((observed["before_units_7d"], observed["after_units_7d"]), (8, 7))
        self.assertEqual((observed["before_revenue_7d"], observed["after_revenue_7d"]), (640000, 560000))
        self.assertEqual((observed["before_gross_profit_7d"], observed["after_gross_profit_7d"]), (320000, 280000))
        self.assertIn("인과", observed["note"])

    def test_input_snapshot_remains_available_after_later_input(self):
        created = self.upload()
        old = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]
        self.assertEqual(old["stock_on_hand"], 10)
        later = b"sku,sale_date,units_sold,revenue,gross_margin\nA-1,2026-09-03,1,80000,40000\n"
        asyncio.run(append_company_sales(created["id"], True,
            UploadFile(filename="next.csv", file=io.BytesIO(later)), self.db))
        update_inputs(created["id"], "A-1", WorkInputPayload(
            as_of_date=date(2026, 9, 3), stock_on_hand=8, inbound_units=0,
            lead_time_days=7, unit_price_krw=80000, unit_cost_krw=40000,
            reorderable=False), self.db)
        self.assertEqual(analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]["stock_on_hand"], 10)
        self.assertEqual(analysis(created["id"], date(2026, 9, 3), None, None, self.db)["products"][0]["stock_on_hand"], 8)

    def test_inbound_counts_only_with_a_date_inside_the_window(self):
        created = self.upload()
        common = dict(as_of_date=date(2026, 9, 2), stock_on_hand=5, inbound_units=40, lead_time_days=7,
                      unit_price_krw=80000, unit_cost_krw=40000, reorderable=True)
        update_inputs(created["id"], "A-1", WorkInputPayload(**common), self.db)
        payload = WorkComparePayload(dataset_id=created["id"], sku="A-1", as_of_date=date(2026, 9, 2),
                                     discount_pct=0, expected_units_30d=30, purchase_units=0)
        undated = compare(payload, self.db)
        self.assertFalse(undated["feasible"])
        self.assertEqual(undated["available_units"], 5)
        self.assertIn("입고 예정일이 없어", undated["excluded_notes"][0])
        update_inputs(created["id"], "A-1", WorkInputPayload(**common, inbound_date=date(2026, 9, 4)), self.db)
        self.assertEqual(analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]["inbound_date"],
                         date(2026, 9, 4))
        early = compare(payload, self.db)
        self.assertTrue(early["feasible"])
        self.assertEqual(early["available_units"], 45)
        update_inputs(created["id"], "A-1", WorkInputPayload(**common, inbound_date=date(2026, 9, 28)), self.db)
        late = compare(payload, self.db)
        self.assertFalse(late["feasible"])
        self.assertEqual(late["available_units"], 45)
        self.assertEqual(late["first_gap_date"], date(2026, 9, 8))
        with self.assertRaises(HTTPException) as error:
            save_decision(WorkDecisionPayload(**payload.model_dump(), action="현재 유지",
                                              rationale="입고 전에 재고가 비는지 확인합니다."), self.db)
        self.assertIn("재고가 비어", error.exception.detail)
        with self.assertRaises(HTTPException):
            update_inputs(created["id"], "A-1", WorkInputPayload(**common, inbound_date=date(2026, 9, 2)), self.db)

    def test_purchase_beyond_lead_window_is_not_available(self):
        created = self.upload()
        update_inputs(created["id"], "A-1", WorkInputPayload(
            as_of_date=date(2026, 9, 2), stock_on_hand=5, inbound_units=0, lead_time_days=45,
            unit_price_krw=80000, unit_cost_krw=40000, reorderable=True), self.db)
        result = compare(WorkComparePayload(dataset_id=created["id"], sku="A-1", as_of_date=date(2026, 9, 2),
                                            discount_pct=0, expected_units_30d=20, purchase_units=100), self.db)
        self.assertFalse(result["feasible"])
        self.assertEqual(result["available_units"], 5)
        self.assertEqual(result["purchase_arrival_date"], date(2026, 10, 17))

    def test_upload_rejects_inbound_date_on_or_before_snapshot(self):
        header = b"sku,name,stock_on_hand,inbound_units,inbound_date\n"
        with self.assertRaises(HTTPException) as error:
            self.upload(products=header + b"A-1,Coat,10,20,2026-09-02\n")
        self.assertIn("inbound_date", error.exception.detail)
        created = self.upload(products=header + b"A-1,Coat,10,20,2026-09-10\n")
        item = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]
        self.assertEqual(item["inbound_date"], date(2026, 9, 10))
    def test_sell_through_needs_a_closing_ledger_and_complete_sales(self):
        created = self.upload()
        common = dict(as_of_date=date(2026, 9, 2), stock_on_hand=10, inbound_units=0, lead_time_days=7,
                      unit_price_krw=80000, unit_cost_krw=40000, reorderable=False)
        item = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]
        self.assertEqual(item["sell_through"]["status"], "missing")
        # 9/1~9/2 sold 3: 8 opening + 5 received − 3 = 10 on hand.
        update_inputs(created["id"], "A-1", WorkInputPayload(
            **common, opening_stock=8, opening_date=date(2026, 9, 1), received_units=5), self.db)
        st = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]["sell_through"]
        self.assertEqual((st["status"], st["pct"], st["sold_units"], st["source"]), ("ok", 23.1, 3, "자사 기록"))
        update_inputs(created["id"], "A-1", WorkInputPayload(
            **common, opening_stock=8, opening_date=date(2026, 9, 1), received_units=9), self.db)
        st = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]["sell_through"]
        self.assertEqual((st["status"], st["pct"], st["difference_units"]), ("mismatch", None, -4))
        dataset = self.db.get(WorkDataset, created["id"])
        dataset.complete_calendar = False
        self.db.commit()
        st = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]["sell_through"]
        self.assertEqual((st["status"], st["pct"]), ("missing", None))
        dataset.kind = "hm"
        self.db.commit()
        st = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]["sell_through"]
        self.assertEqual(st["status"], "not_applicable")

    def test_opening_stock_fields_are_entered_together(self):
        created = self.upload()
        common = dict(as_of_date=date(2026, 9, 2), stock_on_hand=10)
        with self.assertRaises(HTTPException) as error:
            update_inputs(created["id"], "A-1", WorkInputPayload(**common, opening_stock=8), self.db)
        self.assertIn("함께", error.exception.detail)
        with self.assertRaises(HTTPException):
            update_inputs(created["id"], "A-1", WorkInputPayload(
                **common, opening_stock=8, opening_date=date(2026, 9, 2), received_units=0), self.db)
        header = b"sku,name,stock_on_hand,opening_stock,opening_date,received_units\n"
        with self.assertRaises(HTTPException):
            self.upload(products=header + b"A-1,Coat,10,8,,5\n")
        created = self.upload(products=header + b"A-1,Coat,10,8,2026-09-01,5\n")
        st = analysis(created["id"], date(2026, 9, 2), None, None, self.db)["products"][0]["sell_through"]
        self.assertEqual(st["pct"], 23.1)


if __name__ == "__main__":
    unittest.main()
