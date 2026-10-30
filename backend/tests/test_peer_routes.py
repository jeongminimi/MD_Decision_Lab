import unittest
from datetime import date

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.peer_routes import PlanCandidate, SeasonPlanInput, peers, save_season_plan, season_groups, season_review
from app.database import Base
from app.models import (WorkCatalogProduct, WorkCatalogSalesSnapshot, WorkCatalogWeekSale,
                        WorkDataset, WorkSeasonPlan)


class PeerRoutesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.dataset = WorkDataset(name="H&M", kind="hm", start_date=date(2018, 9, 20),
                                   end_date=date(2020, 9, 22), source_note="")
        self.db.add(self.dataset)
        self.db.flush()
        for sku, name, scope, section, category, units in [
            ("001", "Earring A", "accessory", "Womens Small accessories", "Earring", 12),
            ("002", "Earring B", "accessory", "Womens Small accessories", "Earring", 9),
            ("003", "Earring C", "accessory", "Womens Small accessories", "Earring", 0),
            ("004", "Dress A", "apparel", "Womens Dresses", "Dress", 100),
            ("005", "Other scope", "apparel", "Womens Small accessories", "Earring", 100),
        ]:
            self.db.add(WorkCatalogProduct(dataset_id=self.dataset.id, sku=sku, name=name,
                                           section=section, category=category, units_14d=0,
                                           units_30d=0, sales_as_of_date=date(2020, 9, 22)))
            self.db.add(WorkCatalogSalesSnapshot(dataset_id=self.dataset.id, sku=sku,
                as_of_date=date(2020, 8, 31), scope=scope, garment_group="Accessories" if scope == "accessory" else "Dresses Ladies",
                section=section, category=category, units_7d=units, prior_7d=1,
                units_14d=units, prior_14d=2, units_30d=units))
            for year, sold in [(2019, 4), (2020, units)]:
                if sold:
                    self.db.add(WorkCatalogWeekSale(dataset_id=self.dataset.id, sku=sku,
                        year=year, week_index=0, units=sold))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_accessory_ranking_excludes_clothing_and_unknown_stock(self):
        result = peers("001", self.dataset.id, self.db)
        self.assertEqual((result["scope"], result["comparison"]["registered"], result["comparison"]["rank_14d"]),
                         ("accessory", 3, 1))
        self.assertEqual(result["comparison"]["active_14d"], 2)
        self.assertIsNone(result["inventory"])
        self.assertIsNone(result["replenishment"])

    def test_next_season_saves_multiple_accessories_and_frozen_evidence(self):
        group = next(item for item in season_groups(self.dataset.id, self.db) if item["scope"] == "accessory")
        review = season_review(self.dataset.id, group["section"], group["category"], group["scope"], self.db)
        self.assertEqual((review["totals"]["2019"], review["totals"]["2020"]), (12, 21))
        payload = SeasonPlanInput(dataset_id=self.dataset.id, section=group["section"], category=group["category"], scope="accessory",
                                  candidates=[PlanCandidate(sku="001", planned_units=20),
                                              PlanCandidate(sku="002", planned_units=10)],
                                  rationale="올해 같은 상품군 판매 흐름을 검토")
        saved = save_season_plan(payload, self.db)
        plan = self.db.get(WorkSeasonPlan, saved["id"])
        self.assertEqual(plan.planned_units, 30)
        self.assertEqual(plan.sales_snapshot["totals"]["2020"], 21)
        self.assertEqual(len(plan.candidate_skus), 2)

        duplicate = payload.model_copy(update={"candidates": [PlanCandidate(sku="001", planned_units=1),
                                                             PlanCandidate(sku="001", planned_units=2)]})
        with self.assertRaises(HTTPException):
            save_season_plan(duplicate, self.db)
        self.assertEqual(len(self.db.scalars(select(WorkSeasonPlan)).all()), 1)


if __name__ == "__main__":
    unittest.main()
