import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.catalog_routes import catalog
from app.database import Base
from app.models import (WorkCatalogProduct, WorkCatalogSalesSnapshot, WorkDailySale, WorkDataset, WorkInputSnapshot,
                        WorkProduct, WorkSimLedger, WorkSimScenario)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.dataset = WorkDataset(name="H&M", kind="hm", start_date=date(2019, 1, 1),
                                   end_date=date(2020, 9, 22), source_note="", complete_calendar=True)
        self.db.add(self.dataset)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_earlier_decision_date_uses_frozen_sales_and_does_not_leak_later_counts(self):
        for sku, old_units, later_units in [("001", 2, 100), ("002", 20, 1)]:
            self.db.add(WorkCatalogProduct(dataset_id=self.dataset.id, sku=sku, name=f"Item {sku}",
                                           section="Accessories", category="Earring",
                                           units_14d=later_units, units_30d=later_units,
                                           sales_as_of_date=self.dataset.end_date))
            self.db.add(WorkCatalogSalesSnapshot(dataset_id=self.dataset.id, sku=sku,
                as_of_date=date(2020, 8, 31), scope="accessory", garment_group="Accessories",
                section="Accessories", category="Earring", units_7d=old_units,
                prior_7d=0, units_14d=old_units, prior_14d=0, units_30d=old_units))
        self.db.commit()
        result = catalog(self.dataset.id, "", 1, 40, date(2020, 8, 31), False, self.db,
                         sort_by="units_30d", sort_dir="desc")
        self.assertEqual([(row["sku"], row["units_30d"], row["sales_as_of_date"])
                          for row in result["items"]],
                         [("002", 20, date(2020, 8, 31)), ("001", 2, date(2020, 8, 31))])

    def test_full_catalog_search_includes_non_apparel_without_inventing_stock(self):
        self.db.add_all([
            WorkCatalogProduct(dataset_id=self.dataset.id, sku="0000000001", name="Scarf",
                               category="Scarf", section="Accessories", units_14d=3,
                               units_30d=5, sales_as_of_date=date(2020, 9, 22)),
            WorkCatalogProduct(dataset_id=self.dataset.id, sku="0000000002", name="Coat",
                               category="Jacket", section="Womens Jackets", units_14d=8,
                               units_30d=12, sales_as_of_date=date(2020, 9, 22)),
        ])
        self.db.commit()
        result = catalog(self.dataset.id, "Scarf", 1, 40, None, True, self.db)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["section"], "Accessories")
        self.assertEqual(result["items"][0]["units_30d"], 5)
        self.assertIsNone(result["items"][0]["stock_on_hand"])
        self.assertFalse(result["items"][0]["reviewable"])

    def test_simulated_stock_is_labeled_and_only_reviewable_for_sampled_product(self):
        article = WorkCatalogProduct(dataset_id=self.dataset.id, sku="0000000002", name="Coat",
                                     category="Jacket", section="Womens Jackets", units_14d=8,
                                     units_30d=12, sales_as_of_date=date(2020, 9, 22))
        product = WorkProduct(dataset_id=self.dataset.id, sku=article.sku, name="Coat",
                              category="Jacket", section="Womens Jackets")
        scenario = WorkSimScenario(dataset_id=self.dataset.id, name="case", as_of_date=date(2020, 8, 31),
                                   ledger_start=date(2020, 7, 1), ledger_end=date(2020, 9, 22),
                                   source_note="", bias_note="")
        self.db.add_all([article, product, scenario])
        self.db.flush()
        self.db.add(WorkSimLedger(scenario_id=scenario.id, product_id=product.id,
                                  flow_date=scenario.as_of_date, opening_stock=11, inbound_units=0,
                                  observed_units=1, supplied_units=1, shortfall_units=0, closing_stock=10))
        self.db.commit()
        result = catalog(self.dataset.id, "Coat", 1, 40, None, True, self.db)["items"][0]
        self.assertEqual((result["stock_on_hand"], result["stock_source"], result["reviewable"]),
                         (10, "simulation", True))
        observed = catalog(self.dataset.id, "Coat", 1, 40, None, False, self.db)["items"][0]
        self.assertIsNone(observed["stock_on_hand"])

    def test_uploaded_products_include_all_categories_with_observed_sales_and_stock(self):
        self.dataset.kind = "company"
        product = WorkProduct(dataset_id=self.dataset.id, sku="B-1", name="Mug",
                              category="Living", section="Home")
        self.db.add(product)
        self.db.flush()
        self.db.add(WorkDailySale(product_id=product.id, sale_date=date(2020, 9, 20),
                                  channel="online", units=4))
        self.db.add(WorkInputSnapshot(product_id=product.id, as_of_date=self.dataset.end_date,
                                      stock_on_hand=12, source_label="company_upload"))
        self.db.commit()
        result = catalog(self.dataset.id, "Mug", 1, 40, None, False, self.db)
        self.assertEqual(result["total"], 1)
        self.assertEqual((result["items"][0]["units_14d"], result["items"][0]["units_30d"]), (4, 4))
        self.assertEqual(result["items"][0]["stock_on_hand"], 12)
        self.assertTrue(result["items"][0]["reviewable"])

    def test_sorting_applies_before_pagination_for_names_categories_sections_and_sales(self):
        self.db.add_all([
            WorkCatalogProduct(dataset_id=self.dataset.id, sku="1", name="Zebra", category="Tops",
                               section="Women", units_14d=2, units_30d=20,
                               sales_as_of_date=self.dataset.end_date),
            WorkCatalogProduct(dataset_id=self.dataset.id, sku="2", name="Alpha", category="Shoes",
                               section="Men", units_14d=3, units_30d=4,
                               sales_as_of_date=self.dataset.end_date),
            WorkCatalogProduct(dataset_id=self.dataset.id, sku="3", name="Beta", category="Bags",
                               section="Sport", units_14d=1, units_30d=8,
                               sales_as_of_date=self.dataset.end_date),
        ])
        self.db.commit()

        def skus(sort_by, sort_dir, page=1):
            result = catalog(self.dataset.id, "", page, 2, None, False, self.db,
                             sort_by=sort_by, sort_dir=sort_dir)
            return [item["sku"] for item in result["items"]]

        self.assertEqual(skus("name", "asc"), ["2", "3"])
        self.assertEqual(skus("name", "desc"), ["1", "3"])
        self.assertEqual(skus("category", "asc"), ["3", "2"])
        self.assertEqual(skus("section", "asc"), ["2", "3"])
        self.assertEqual(skus("units_30d", "desc"), ["1", "3"])
        self.assertEqual(skus("units_30d", "desc", 2), ["2"])
        self.assertEqual(skus("units_30d", "asc"), ["2", "3"])

    def test_stock_sort_keeps_missing_last_in_both_directions(self):
        products = [
            WorkProduct(dataset_id=self.dataset.id, sku=sku, name=name,
                        category="Jacket", section="Women")
            for sku, name in [("1", "Low"), ("2", "High")]
        ]
        self.db.add_all(products)
        self.db.add_all([
            WorkCatalogProduct(dataset_id=self.dataset.id, sku=sku, name=name,
                               category="Jacket", section="Women", units_14d=1,
                               units_30d=2, sales_as_of_date=self.dataset.end_date)
            for sku, name in [("1", "Low"), ("2", "High"), ("3", "Unknown")]
        ])
        scenario = WorkSimScenario(dataset_id=self.dataset.id, name="case", as_of_date=date(2020, 8, 31),
                                   ledger_start=date(2020, 7, 1), ledger_end=date(2020, 9, 22),
                                   source_note="", bias_note="")
        self.db.add(scenario)
        self.db.flush()
        for product, units in zip(products, [5, 20]):
            self.db.add(WorkSimLedger(scenario_id=scenario.id, product_id=product.id,
                                      flow_date=scenario.as_of_date, opening_stock=units,
                                      inbound_units=0, observed_units=0, supplied_units=0,
                                      shortfall_units=0, closing_stock=units))
        self.db.commit()

        for direction, expected in [("desc", ["2", "1", "3"]), ("asc", ["1", "2", "3"])]:
            result = catalog(self.dataset.id, "", 1, 40, None, True, self.db,
                             sort_by="stock", sort_dir=direction)
            self.assertEqual([item["sku"] for item in result["items"]], expected)

    def test_company_sales_and_stock_sort_use_requested_day(self):
        self.dataset.kind = "company"
        products = [WorkProduct(dataset_id=self.dataset.id, sku=sku, name=name,
                                category="Living", section="Home")
                    for sku, name in [("A", "A"), ("B", "B"), ("C", "C")]]
        self.db.add_all(products)
        self.db.flush()
        for product, units in zip(products[:2], [2, 10]):
            self.db.add(WorkDailySale(product_id=product.id, sale_date=date(2020, 9, 20),
                                      channel="online", units=units))
        for product, stock in zip(products[:2], [40, 3]):
            self.db.add(WorkInputSnapshot(product_id=product.id, as_of_date=self.dataset.end_date,
                                          stock_on_hand=stock, source_label="company_upload"))
        self.db.commit()

        sold = catalog(self.dataset.id, "", 1, 40, None, False, self.db,
                       sort_by="units_30d", sort_dir="desc")
        self.assertEqual([item["sku"] for item in sold["items"]], ["B", "A", "C"])
        stocked = catalog(self.dataset.id, "", 1, 40, None, False, self.db,
                          sort_by="stock", sort_dir="asc")
        self.assertEqual([item["sku"] for item in stocked["items"]], ["B", "A", "C"])
