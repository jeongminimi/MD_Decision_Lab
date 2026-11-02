import unittest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import WorkDataset, WorkProduct, WorkSimDecision, WorkSimScenario


class OperationFlowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        dataset = WorkDataset(name="test", kind="hm", start_date=date(2020, 8, 1),
                              end_date=date(2020, 9, 22), source_note="test")
        self.db.add(dataset)
        self.db.flush()
        product = WorkProduct(dataset_id=dataset.id, sku="0000000001", name="상품")
        self.db.add(product)
        self.db.flush()
        scenario = WorkSimScenario(dataset_id=dataset.id, name="test case", as_of_date=date(2020, 8, 31),
            ledger_start=date(2020, 8, 1), ledger_end=date(2020, 9, 22), source_note="test", bias_note="test")
        self.db.add(scenario)
        self.db.flush()
        self.dataset_id = dataset.id
        self.product_id = product.id
        self.db.add_all([
            WorkSimDecision(scenario_id=scenario.id, product_id=product.id, as_of_date=date(2020, 8, 31),
                action="추가 매입 검토", rationale="재고 소진 검토", snapshot={"comparison": {
                    "stock_on_hand": 10, "purchase_units": 100, "purchase_arrival_date": "2020-09-04",
                    "expected_units_30d": 20, "estimated_revenue_krw": None,
                    "estimated_gross_profit_krw": None, "unit_cost_krw": 5000, "discount_pct": 0}}),
            WorkSimDecision(scenario_id=scenario.id, product_id=product.id, as_of_date=date(2020, 8, 31),
                action="온라인 기획전 검토", rationale="기획전 판매 검토", snapshot={"comparison": {
                    "stock_on_hand": 50, "expected_units_30d": 30, "estimated_revenue_krw": 300000,
                    "estimated_gross_profit_krw": 150000, "unit_cost_krw": 5000,
                    "discount_pct": 10}}),
        ])
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def test_partial_receipt_and_sale_update_stock_without_duplicate(self):
        response = self.client.post("/api/work/operations", json={"decision_source": "sim", "decision_id": 1,
            "planned_start": "2020-09-02", "planned_units": 100, "expected_receipt_date": "2020-09-04"})
        self.assertEqual(response.status_code, 200, response.text)
        op = response.json()
        self.assertEqual(op["current_stock"], 10)
        receipt = {"event_date": "2020-09-06", "kind": "received", "units": 80, "client_key": "receipt-1"}
        first = self.client.post(f"/api/work/operations/{op['id']}/events", json=receipt)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["current_stock"], 90)
        self.assertEqual(first.json()["status"], "partial")
        repeated = self.client.post(f"/api/work/operations/{op['id']}/events", json=receipt)
        self.assertEqual(repeated.json()["received_units"], 80)
        sale = self.client.post(f"/api/work/operations/{op['id']}/events", json={
            "event_date": "2020-09-07", "kind": "sale", "units": 5, "client_key": "sale-1"})
        self.assertEqual(sale.json()["current_stock"], 85)
        self.assertEqual(sale.json()["events"][-1]["stock_after"], 85)
        campaign = self.client.post("/api/work/operations", json={"decision_source": "sim", "decision_id": 2,
            "planned_start": "2020-09-02", "planned_end": "2020-09-08"})
        self.assertEqual(campaign.json()["current_stock"], 85)
        excess = self.client.post(f"/api/work/operations/{op['id']}/events", json={
            "event_date": "2020-09-08", "kind": "received", "units": 21})
        self.assertEqual(excess.status_code, 400)

    def test_campaign_records_forecast_and_result_separately(self):
        response = self.client.post("/api/work/operations", json={"decision_source": "sim", "decision_id": 2,
            "planned_start": "2020-09-02", "planned_end": "2020-09-08"})
        self.assertEqual(response.status_code, 200, response.text)
        op = response.json()
        self.assertEqual(op["expected_sales_units"], 30)
        self.assertEqual(op["expected_period_units"], 7)
        self.assertEqual(op["expected_period_revenue_krw"], 70000)
        sale = self.client.post(f"/api/work/operations/{op['id']}/events", json={
            "event_date": "2020-09-04", "kind": "sale", "units": 12,
            "revenue_krw": 120000, "client_key": "campaign-sale"})
        self.assertEqual(sale.status_code, 200, sale.text)
        self.assertEqual(sale.json()["recorded_sales_units"], 12)
        self.assertEqual(sale.json()["recorded_profit_krw"], 60000)
        self.assertEqual(sale.json()["expected_sales_units"], 30)
        outside = self.client.post(f"/api/work/operations/{op['id']}/events", json={
            "event_date": "2020-09-09", "kind": "sale", "units": 1})
        self.assertEqual(outside.status_code, 400)


if __name__ == "__main__":
    unittest.main()
