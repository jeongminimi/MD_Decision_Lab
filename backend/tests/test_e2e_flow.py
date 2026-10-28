import os
import shutil
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import ensure_schema_compatibility, get_db
from app.main import app

REAL_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "md_decision_lab.db"))


def count_real_db_decisions() -> int:
    if not os.path.exists(REAL_DB_PATH):
        return 0
    conn = sqlite3.connect(REAL_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM fashion_decisions")
        return cur.fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()


class EndToEndFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial_real_count = count_real_db_decisions()

    def setUp(self):
        # 1. Create a dedicated temporary SQLite DB file copied from the real DB (if exists)
        # to ensure zero side-effects on md_decision_lab.db while keeping sample data.
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()
        self.temp_db_path = temp_file.name

        if os.path.exists(REAL_DB_PATH):
            shutil.copyfile(REAL_DB_PATH, self.temp_db_path)

        self.test_engine = create_engine(
            f"sqlite:///{self.temp_db_path}",
            connect_args={"check_same_thread": False},
        )
        ensure_schema_compatibility(self.test_engine)
        self.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)

        def override_get_db():
            db = self.TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.test_engine.dispose()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

        # Verify real DB isolation: count must remain strictly identical
        current_real_count = count_real_db_decisions()
        self.assertEqual(
            current_real_count,
            self.initial_real_count,
            f"실제 앱 DB(md_decision_lab.db)의 기록 수가 테스트 전({self.initial_real_count})과 후({current_real_count})에 달라졌습니다.",
        )

    def test_full_scenario_flow_and_persistence(self):
        # 1. Check status and ensure sample imported
        status_res = self.client.get("/api/fashion/status")
        self.assertEqual(status_res.status_code, 200)
        if not status_res.json()["imported"]:
            import_res = self.client.post("/api/fashion/import-sample")
            self.assertEqual(import_res.status_code, 200)

        # 2. Case Selection (사례 열기 / 근거 확인)
        analysis_res = self.client.get("/api/fashion/analysis?as_of=2026-08-31")
        self.assertEqual(analysis_res.status_code, 200)
        data = analysis_res.json()
        self.assertEqual(len(data["products"]), 30)

        target_sku = "FSH-SS-001"
        target_prod = next(p for p in data["products"] if p["sku"] == target_sku)
        self.assertEqual(target_prod["stock_on_hand"], 145)

        # 3. Option Comparison (결과 비교)
        compare_payload = {
            "sku": target_sku,
            "options": [
                {"label": "A · 현재 가격 유지", "discount_pct": 0, "expected_units_30d": target_prod["units_30d"], "purchase_units": 0},
                {"label": "B · 변경안", "discount_pct": 15, "expected_units_30d": 40, "purchase_units": 0},
            ]
        }
        comp_res = self.client.post("/api/fashion/compare-options", json=compare_payload)
        self.assertEqual(comp_res.status_code, 200)
        comp_data = comp_res.json()
        opt_b = comp_data["options"][1]
        self.assertTrue(opt_b["feasible"])
        self.assertEqual(opt_b["unit_price"], 41650.0)  # 49000 * 0.85
        # cost=18000, margin_per_unit = 23650, profit = 40 * 23650 = 946000
        self.assertEqual(opt_b["estimated_gross_profit"], 946000.0)

        # 4. Save Decision with malicious/falsified client numbers (판단 저장)
        # Server must ignore client's falsified values and store server-recalculated values
        save_payload = {
            "sku": target_sku,
            "action_type": "option_b",
            "chosen_option": "B",
            "discount_pct": 15.0,
            "expected_units_30d": 40,
            "purchase_units": 0,
            "estimated_revenue": 99999999.0,  # falsified
            "estimated_gross_profit": 88888888.0,  # falsified
            "estimated_remaining_stock": 999,  # falsified
            "feasible": False,  # falsified
            "rationale": "15% 할인 적용 시 40장 판매하여 매출총이익 94.6만원 달성을 검토한다."
        }
        save_res = self.client.post("/api/fashion/decisions", json=save_payload)
        self.assertEqual(save_res.status_code, 200)
        saved = save_res.json()
        self.assertEqual(saved["chosen_option"], "B")
        self.assertEqual(saved["discount_pct"], 15.0)
        self.assertEqual(saved["expected_units_30d"], 40)
        self.assertEqual(saved["estimated_revenue"], 1666000.0)  # 41650 * 40
        self.assertEqual(saved["estimated_gross_profit"], 946000.0)  # Correct server value!
        self.assertEqual(saved["estimated_remaining_stock"], 105)  # 145 - 40
        self.assertTrue(saved["feasible"])

        # 5. Refresh Verification (새로고침 후 기록 확인)
        list_res = self.client.get("/api/fashion/decisions")
        self.assertEqual(list_res.status_code, 200)
        history = list_res.json()
        latest = next(d for d in history if d["id"] == saved["id"])
        self.assertEqual(latest["sku"], target_sku)
        self.assertEqual(latest["chosen_option"], "B")
        self.assertEqual(latest["estimated_gross_profit"], 946000.0)
        self.assertEqual(latest["rationale"], save_payload["rationale"])

        # 6. Verify Discontinued Item Purchase Rejection
        discontinued_payload = {
            "sku": "FSH-EV-001",
            "action_type": "option_b",
            "chosen_option": "B",
            "discount_pct": 20.0,
            "expected_units_30d": 20,
            "purchase_units": 10,  # Not allowed
            "rationale": "재발주 불가 상품에 추가 매입 시도"
        }
        disc_res = self.client.post("/api/fashion/decisions", json=discontinued_payload)
        self.assertEqual(disc_res.status_code, 400)
        self.assertIn("재발주가 불가능", disc_res.json()["detail"])

        # 7. Verify Hold Option Wipes Arbitrary Metrics
        hold_payload = {
            "sku": "FSH-FW-001",
            "action_type": "hold",
            "chosen_option": "hold",
            "discount_pct": 10.0,
            "expected_units_30d": 50,
            "purchase_units": 20,
            "estimated_revenue": 10000000.0,
            "estimated_gross_profit": 5000000.0,
            "rationale": "출시 전 상태 점검을 위해 일단 결정을 보류한다."
        }
        hold_res = self.client.post("/api/fashion/decisions", json=hold_payload)
        self.assertEqual(hold_res.status_code, 200)
        hold_data = hold_res.json()
        self.assertEqual(hold_data["chosen_option"], "hold")
        self.assertIsNone(hold_data["discount_pct"])
        self.assertIsNone(hold_data["expected_units_30d"])
        self.assertEqual(hold_data["purchase_units"], 0)
        self.assertIsNone(hold_data["estimated_revenue"])
        self.assertIsNone(hold_data["estimated_gross_profit"])
        self.assertIsNone(hold_data["estimated_remaining_stock"])
        self.assertIsNone(hold_data["feasible"])

    def test_e2e_contradiction_rejections(self):
        # Contradictions must return 400
        cases = [
            ("option_a", "B"),
            ("option_b", "A"),
            ("hold", "B"),
            ("hold", "A"),
        ]
        for action, chosen in cases:
            res = self.client.post("/api/fashion/decisions", json={
                "sku": "FSH-SS-001",
                "action_type": action,
                "chosen_option": chosen,
                "rationale": "모순 테스트"
            })
            self.assertEqual(res.status_code, 400)
            self.assertIn("모순", res.json()["detail"])

    def test_e2e_infeasible_stockout_decision(self):
        # Target: FSH-SS-001 (stock 145). Request 250 units without purchase -> shortfall=105 -> feasible=False
        res = self.client.post("/api/fashion/decisions", json={
            "sku": "FSH-SS-001",
            "action_type": "option_b",
            "chosen_option": "B",
            "discount_pct": 20.0,
            "expected_units_30d": 250,
            "purchase_units": 0,
            "estimated_revenue": 1000000.0,  # Falsified by client
            "estimated_gross_profit": 500000.0,  # Falsified by client
            "rationale": "재고 부족 상황에서 성과 지표는 null로 처리되어야 함"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["feasible"])
        self.assertIsNone(data["estimated_revenue"])
        self.assertIsNone(data["estimated_gross_profit"])
        self.assertIsNone(data["estimated_remaining_stock"])


if __name__ == "__main__":
    unittest.main()
