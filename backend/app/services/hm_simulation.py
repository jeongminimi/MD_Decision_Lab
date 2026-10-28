"""Import the bundled H&M operating simulation (sample_data/hm_operating_case) next to observed H&M sales.

Observed units must match work_daily_sales exactly; inventory, orders and prices are stored in separate
work_sim_* tables and are never written into the company upload path or the observed sales table.
"""

import csv
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (WorkDailySale, WorkDataset, WorkProduct, WorkSimLedger, WorkSimPolicy, WorkSimPrice,
                      WorkSimPurchaseOrder, WorkSimScenario)

CASE_DIR = Path(__file__).resolve().parents[3] / "sample_data" / "hm_operating_case"
SCENARIO_NAME = "H&M 운영 시뮬레이션 · 가상 정책 v2"
AS_OF = date(2020, 8, 31)
LEDGER_START = date(2020, 7, 1)
LEDGER_END = date(2020, 9, 22)
SOURCE_NOTE = ("판매 수량은 H&M 관측값. 재고·발주·원화 가격·원가·시즌 상태는 가상 운영 조건이며, "
               "재고 위험·공급 부족분·매출총이익은 이 조건으로 계산한 시뮬레이션 결과입니다. 실제 H&M 재고·실적이 아닙니다.")
BIAS_NOTE = ("표본 범위: H&M 작업공간의 상품은 2019·2020년 7월 1일~8월 31일 판매 상위 상품입니다. "
             "판단 기준일(8월 31일) 이후 판매는 선정에 쓰지 않았습니다. 여름 판매 상위 상품만 모은 표본이라 "
             "H&M 전체를 대표하지 않으며, 9월에 처음 팔리기 시작한 신상은 포함되지 않습니다.")
LIFECYCLES = {"fall_new_scenario", "summer_clearance_scenario", "winter_carryover_scenario", "unassigned"}


def _read(directory: Path, name: str) -> list[dict[str, str]]:
    # 모든 값을 문자열로 읽어 SKU 앞자리 0을 보존한다.
    with (directory / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _day(value: str) -> date:
    return date.fromisoformat(value)


def import_simulation(db: Session, dataset_id: int, case_dir: Path | None = None) -> WorkSimScenario:
    """Validate every file against the stored H&M sales, then save all rows or nothing."""
    case_dir = case_dir or CASE_DIR
    dataset = db.get(WorkDataset, dataset_id)
    if dataset is None or dataset.kind != "hm":
        raise LookupError("H&M 작업공간을 찾지 못했습니다.")
    if db.scalar(select(WorkSimScenario.id).where(WorkSimScenario.dataset_id == dataset_id,
                                                  WorkSimScenario.name == SCENARIO_NAME)) is not None:
        raise FileExistsError("이미 연결된 시뮬레이션입니다. 기존 자료를 덮어쓰지 않았습니다.")

    policy = _read(case_dir, "hm_product_policy.csv")
    ledger = _read(case_dir, "hm_inventory_ledger.csv")
    orders = _read(case_dir, "hm_purchase_orders.csv")
    prices = _read(case_dir, "hm_economics.csv")

    products = {p.sku: p for p in db.scalars(select(WorkProduct).where(WorkProduct.dataset_id == dataset_id))}
    skus = [row["sku"] for row in policy]
    if len(skus) != len(set(skus)) or not 40 <= len(skus) <= 60:
        raise ValueError("정책 파일의 SKU 수 또는 중복을 확인하세요.")
    bad = [sku for sku in skus if not re.fullmatch(r"\d{10}", sku) or sku not in products]
    if bad:
        raise ValueError(f"H&M 작업공간 상품 ID와 연결되지 않는 SKU: {', '.join(bad[:5])}")
    ids = {sku: products[sku].id for sku in skus}

    stop_dates: dict[str, date | None] = {}
    for row in policy:
        if row["scenario_lifecycle"] not in LIFECYCLES or row["reorderable_assumed"] not in {"true", "false"}:
            raise ValueError(f"{row['sku']}: 상품 상태 또는 재발주 가정 값이 잘못됐습니다.")
        match = re.search(r"재발주 불가 설정일=(\d{4}-\d{2}-\d{2})", row["assumption_reason"])
        if row["reorderable_assumed"] == "false" and match is None:
            raise ValueError(f"{row['sku']}: 재발주 불가 설정일이 없습니다.")
        stop_dates[row["sku"]] = _day(match.group(1)) if match else None
        first = db.scalar(select(func.min(WorkDailySale.sale_date)).where(
            WorkDailySale.product_id == ids[row["sku"]], WorkDailySale.sale_date <= AS_OF, WorkDailySale.units > 0))
        if (first.isoformat() if first else "") != row["observed_first_sale_date"]:
            raise ValueError(f"{row['sku']}: 처음 관측된 판매일이 DB와 다릅니다.")

    observed: Counter = Counter()
    for product_id, day, units in db.execute(
            select(WorkDailySale.product_id, WorkDailySale.sale_date, func.sum(WorkDailySale.units))
            .where(WorkDailySale.product_id.in_(ids.values()), WorkDailySale.sale_date.between(LEDGER_START, LEDGER_END))
            .group_by(WorkDailySale.product_id, WorkDailySale.sale_date)):
        observed[(product_id, day)] = units

    by_sku: dict[str, list[dict]] = defaultdict(list)
    for row in ledger:
        if row["sku"] not in ids:
            raise ValueError(f"수불 파일의 SKU {row['sku']}가 정책 파일에 없습니다.")
        by_sku[row["sku"]].append(row)
    expected_days = [LEDGER_START + timedelta(i) for i in range((LEDGER_END - LEDGER_START).days + 1)]
    ledger_rows, inbound = [], Counter()
    for sku in skus:
        previous = None
        rows = by_sku.get(sku, [])
        if [_day(r["date"]) for r in rows] != expected_days:
            raise ValueError(f"{sku}: 수불 날짜가 {LEDGER_START}~{LEDGER_END} 연속이 아닙니다.")
        for r in rows:
            day = _day(r["date"])
            o, i, s, sup, short, c = (int(r[k]) for k in (
                "opening_stock_synthetic", "inbound_units_synthetic", "units_sold_observed",
                "units_supplied_synthetic", "supply_shortfall_synthetic", "closing_stock_synthetic"))
            if s != observed.get((ids[sku], day), 0):
                raise ValueError(f"{sku} {day}: 수불의 판매량이 H&M 관측 판매와 다릅니다.")
            if min(o, i, c, short) < 0 or sup != min(s, o + i) or short != s - sup or o + i - sup != c:
                raise ValueError(f"{sku} {day}: 수불식 또는 공급 부족분 계산이 맞지 않습니다.")
            if day <= AS_OF and short:
                raise ValueError(f"{sku} {day}: 기준일 이전에는 관측 판매를 모두 공급해야 합니다.")
            if previous is not None and o != previous:
                raise ValueError(f"{sku} {day}: 전날 기말재고와 기초재고가 다릅니다.")
            previous = c
            if i:
                inbound[(sku, day)] = i
            ledger_rows.append(WorkSimLedger(product_id=ids[sku], flow_date=day, opening_stock=o, inbound_units=i,
                                             observed_units=s, supplied_units=sup, shortfall_units=short,
                                             closing_stock=c))

    receipts, order_rows = Counter(), []
    for row in orders:
        sku = row["sku"]
        if sku not in ids:
            raise ValueError(f"발주 파일의 SKU {sku}가 정책 파일에 없습니다.")
        if row["status"] not in {"received", "open"}:
            raise ValueError(f"{row['po_id']}: 계획 발주만 가져올 수 있습니다(상태 {row['status']}).")
        ordered_on = _day(row["order_date_assumed"]) if row["order_date_assumed"] else None
        if ordered_on is None or ordered_on > AS_OF:
            raise ValueError(f"{row['po_id']}: 발주일이 없거나 기준일 이후입니다.")
        if stop_dates[sku] is not None and ordered_on >= stop_dates[sku]:
            raise ValueError(f"{row['po_id']}: 재발주 불가 설정일 이후의 발주입니다.")
        ordered, received = int(row["ordered_units_synthetic"]), int(row["received_units_synthetic"])
        actual = _day(row["actual_receipt_date_assumed"]) if row["actual_receipt_date_assumed"] else None
        if row["status"] == "received":
            if actual is None or not received or received > ordered:
                raise ValueError(f"{row['po_id']}: 입고 수량·날짜를 확인하세요.")
            receipts[(sku, actual)] += received
        elif received or actual is not None or _day(row["expected_receipt_date_assumed"]) <= LEDGER_END:
            raise ValueError(f"{row['po_id']}: 미입고 발주의 상태가 맞지 않습니다.")
        order_rows.append(WorkSimPurchaseOrder(
            product_id=ids[sku], po_code=row["po_id"], order_date=ordered_on,
            expected_receipt_date=_day(row["expected_receipt_date_assumed"]), actual_receipt_date=actual,
            ordered_units=ordered, received_units=received, status=row["status"],
            assumption_reason=row["assumption_reason"]))
    if receipts != inbound:
        raise ValueError("발주 입고와 수불 입고가 일치하지 않습니다.")

    price_rows, segments = [], defaultdict(list)
    for row in prices:
        sku = row["sku"]
        if sku not in ids:
            raise ValueError(f"가격 파일의 SKU {sku}가 정책 파일에 없습니다.")
        lp, sp, uc = (float(row[k]) for k in ("list_price_krw_assumed", "selling_price_krw_assumed", "unit_cost_krw_assumed"))
        if not 0 < uc < sp <= lp:
            raise ValueError(f"{sku}: 가격·원가 관계를 확인하세요.")
        segments[sku].append((_day(row["valid_from"]), _day(row["valid_to"])))
        price_rows.append(WorkSimPrice(product_id=ids[sku], valid_from=_day(row["valid_from"]), valid_to=_day(row["valid_to"]),
                                       list_price_krw=lp, selling_price_krw=sp, unit_cost_krw=uc,
                                       price_tier_rule=row["price_tier_rule"], cost_rule=row["cost_rule"]))
    for sku in skus:
        spans = sorted(segments.get(sku, []))
        if not spans or spans[0][0] != LEDGER_START or spans[-1][1] != LEDGER_END or any(
                a[1] + timedelta(1) != b[0] for a, b in zip(spans, spans[1:])):
            raise ValueError(f"{sku}: 가격 적용 기간이 수불 기간을 빈틈없이 덮지 않습니다.")

    scenario = WorkSimScenario(dataset_id=dataset_id, name=SCENARIO_NAME, as_of_date=AS_OF,
                               ledger_start=LEDGER_START, ledger_end=LEDGER_END,
                               source_note=SOURCE_NOTE, bias_note=BIAS_NOTE)
    try:
        db.add(scenario)
        db.flush()
        for row in policy:
            db.add(WorkSimPolicy(
                scenario_id=scenario.id, product_id=ids[row["sku"]],
                observed_first_sale_date=_day(row["observed_first_sale_date"]) if row["observed_first_sale_date"] else None,
                scenario_lifecycle=row["scenario_lifecycle"], reorderable=row["reorderable_assumed"] == "true",
                reorder_stop_date=stop_dates[row["sku"]], lead_time_days=int(row["lead_time_days_assumed"]),
                selection_reason=row["selection_reason"], assumption_reason=row["assumption_reason"]))
        for item in [*ledger_rows, *order_rows, *price_rows]:
            item.scenario_id = scenario.id
            db.add(item)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return scenario
