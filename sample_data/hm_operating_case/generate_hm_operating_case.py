"""H&M 관측 판매를 제약조건으로 삼는 가상 운영 사례 생성기.

H&M 원본에는 재고·발주·원가·원화 가격이 없다. 이 스크립트는 그 값을 실제처럼 복원하지 않는다.
DB에 이미 적재된 H&M 일별·채널별 판매(관측값)는 그대로 두고, 그 판매를 감당하도록
미리 정한 규칙으로 가상 재고 수불·발주·가격을 만든다.

실행 (MD_Decision_Lab/ 에서):
    python sample_data/hm_operating_case/generate_hm_operating_case.py
    python sample_data/hm_operating_case/verify_hm_operating_case.py

DB는 읽기 전용(mode=ro)으로만 연다. 기존 DB·코드·원본 ZIP은 수정하지 않는다.
"""

import argparse
import csv
import random
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from math import ceil
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parents[1] / "backend" / "md_decision_lab.db"
SEED = 20200831
AS_OF = date(2020, 8, 31)            # 분석 기준일. 선정·8/31 재고 설정은 이 날짜까지의 판매만 사용
LEDGER_START = date(2020, 7, 1)
LEDGER_END = date(2020, 9, 22)       # 09-01~09-22는 관측 결과 확인용(holdout)
DATASET_NAME = "H&M 실제 판매 · MD 시연"

# 선정 버킷과 목표 수량 (합계 50 내외)
QUOTAS = {"pre_sale": 99, "winter_carryover": 6, "new_observed": 10, "declining": 10,
          "rising": 8, "low_sales": 6, "stable": 6}
SUMMER_CATEGORIES = {"Shorts", "Vest top", "Dress", "T-shirt", "Top", "Skirt", "Bodysuit"}
FALL_CATEGORIES = {"Jacket", "Coat", "Blazer", "Sweater", "Cardigan", "Trousers", "Shirt", "Blouse"}

# 가정값: 리드타임(일), 정가(원), 원가율. 실제 H&M 값이 아님
LEAD_TIME = {"Jacket": 35, "Coat": 35, "Blazer": 35,
             "Trousers": 28, "Sweater": 28, "Cardigan": 28, "Dress": 28}
DEFAULT_LEAD_TIME = 21
LIST_PRICE = {"Coat": 129000, "Jacket": 99000, "Blazer": 79000, "Dress": 49000, "Trousers": 45000,
              "Sweater": 39000, "Cardigan": 39000, "Shirt": 35000, "Blouse": 35000, "Skirt": 35000,
              "Shorts": 29000, "Top": 19900, "Bodysuit": 19900, "T-shirt": 14900, "Vest top": 12900}
COST_RATIO = 0.38
SUMMER_MARKDOWN = (date(2020, 8, 1), 0.30)     # 여름 잔여: 8/1부터 30% 인하 (가정)
CARRYOVER_DISCOUNT = 0.40                      # 작년 겨울 행사: 기간 전체 40% 인하 (가정)

# 발주 규칙 (가정): 매주 월요일 검토, 목표재고 = 최근 28일 평균 × (리드타임 + 7 + 안전 7일)
SAFETY_DAYS = 7
MOQ = 30
PACK = 10
PRESALE_RECEIPT = date(2020, 8, 24)            # 기준일까지 판매 미관측 상품의 초도 입고일 (가정)
NON_REORDER_BUFFER = 1.5                       # 재발주 불가 상품의 기준일 재고 하한 배수 (가정)


def day_range(start: date, end: date):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def round_pack(value: float) -> int:
    return int(ceil(value / PACK) * PACK)


def load(db_path: Path):
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT id FROM work_datasets WHERE kind='hm' AND name=?", (DATASET_NAME,)).fetchone()
        if row is None:
            raise SystemExit("H&M 시연 작업공간을 DB에서 찾지 못했습니다.")
        dataset_id = row[0]
        products = {pid: {"sku": sku, "name": name, "section": section, "category": category}
                    for pid, sku, name, section, category in con.execute(
                        "SELECT id, sku, name, section, category FROM work_products WHERE dataset_id=?",
                        (dataset_id,))}
        sales: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
        for pid, day, units in con.execute(
                "SELECT product_id, sale_date, SUM(units) FROM work_daily_sales "
                "WHERE product_id IN (SELECT id FROM work_products WHERE dataset_id=?) "
                "GROUP BY product_id, sale_date", (dataset_id,)):
            sales[products[pid]["sku"]][date.fromisoformat(day)] += units
    finally:
        con.close()
    return {p["sku"]: p for p in products.values()}, sales


def window(series: dict[date, int], start: date, end: date) -> int:
    return sum(units for day, units in series.items() if start <= day <= end)


def profile(series: dict[date, int]) -> dict:
    """기준일(08-31)까지의 관측 판매만 사용한다."""
    observed = [day for day, units in series.items() if day <= AS_OF and units > 0]
    return {
        "first": min(observed) if observed else None,
        "u14": window(series, AS_OF - timedelta(13), AS_OF),
        "p14": window(series, AS_OF - timedelta(27), AS_OF - timedelta(14)),
        "u30": window(series, AS_OF - timedelta(29), AS_OF),
        "winter": window(series, date(2019, 11, 1), date(2020, 2, 29)),
    }


def bucket(product: dict, stats: dict) -> str:
    if stats["first"] is None:
        return "pre_sale"
    if (product["category"] in {"Coat", "Jacket"} and stats["winter"] >= 50
            and 1 <= stats["u30"] and stats["winter"] >= 3 * stats["u30"]):
        return "winter_carryover"
    if stats["first"] >= LEDGER_START:
        return "new_observed"
    if stats["p14"] >= 5 and stats["u14"] <= stats["p14"] * 0.7:
        return "declining"
    if stats["u14"] >= 5 and stats["u14"] >= max(1, stats["p14"]) * 1.3:
        return "rising"
    if stats["u30"] < 10:
        return "low_sales"
    return "stable"


def select(products: dict, sales: dict, rng: random.Random) -> list[tuple[str, str, dict]]:
    pools: dict[str, list] = defaultdict(list)
    for sku in sorted(products):
        stats = profile(sales.get(sku, {}))
        pools[bucket(products[sku], stats)].append((sku, stats))
    chosen = []
    for name, quota in QUOTAS.items():
        pool = pools[name]
        rng.shuffle(pool)
        by_section: dict[str, list] = defaultdict(list)
        for sku, stats in pool:
            by_section[products[sku]["section"]].append((sku, stats))
        picked = []
        while len(picked) < quota and any(by_section.values()):      # 섹션 순환으로 고르게 선정
            for section in sorted(by_section):
                if by_section[section] and len(picked) < quota:
                    picked.append(by_section[section].pop(0))
        chosen += [(sku, name, stats) for sku, stats in sorted(picked)]
    return chosen


def lifecycle(product: dict, name: str, stats: dict) -> tuple[str, str]:
    if name == "winter_carryover":
        return "winter_carryover_scenario", (
            f"코트·재킷, 2019-11~2020-02 관측 판매 {stats['winter']}개가 기준일 직전 30일 {stats['u30']}개의 3배 이상")
    if name == "pre_sale":
        return "fall_new_scenario", "기준일까지 판매 미관측 상품을 가을 신상 출시 전으로 가정"
    if name == "new_observed" and product["category"] in FALL_CATEGORIES:
        return "fall_new_scenario", f"2020-07-01 이후 처음 관측({stats['first']}) + 가을 착용 가능 상품 종류"
    if (name == "declining" and product["category"] in SUMMER_CATEGORIES
            and stats["first"] < date(2020, 6, 1)):
        return "summer_clearance_scenario", "여름 상품 종류 + 최근 2주 판매가 직전 2주 대비 30% 이상 감소"
    return "unassigned", "관측 판매만으로 시즌 상태를 뒷받침하기 어려워 부여하지 않음"


def trailing_rate(series: dict[date, int], day: date, first: date | None) -> float:
    """day 전날까지의 최근 28일 평균. 처음 관측 후 28일 미만이면 관측 일수(최소 7일)로 나눈다."""
    if first is None or first >= day:
        return 0.0
    start = max(day - timedelta(28), first)
    days = max(7, (day - start).days)
    return window(series, start, day - timedelta(1)) / days


def simulate(policy: dict, series: dict[date, int], initial: dict):
    """한 SKU의 가상 수불. 발주는 기준일까지만, 그날 이전의 판매만 보고 낸다.

    관측 판매가 가상 가용 재고를 넘으면 재고를 음수로 두지 않고, 넘친 수량을
    '가상 정책상 공급 부족분'으로 따로 센다. 이 값은 실제 H&M 품절이나 잃은 매출이 아니다.
    """
    lead, first = policy["lead_time"], policy["first"]
    stop_orders = policy["no_order_after"]
    stock = initial["opening"]
    pipeline: dict[date, list] = defaultdict(list)
    orders = []
    for po in initial["pos"]:
        pipeline[po["receipt"]].append(po)
        orders.append(po)
    ledger = []
    for day in day_range(LEDGER_START, LEDGER_END):
        # 월요일 검토 → 발주 (기준일까지, 재발주 가능하고 설정일 이전일 때만)
        if (day.weekday() == 0 and day <= AS_OF and (stop_orders is None or day <= stop_orders)
                and first is not None and first < day):
            rate = trailing_rate(series, day, first)
            on_order = sum(po["qty"] for po in orders if po["receipt"] >= day and po["order"] <= day)
            target = rate * (lead + 7 + SAFETY_DAYS)
            need = target - (stock + on_order)
            if rate > 0 and need > 0:
                qty = max(MOQ, round_pack(need))
                po = {"order": day, "receipt": day + timedelta(lead), "qty": qty, "kind": "policy"}
                orders.append(po)
                pipeline[po["receipt"]].append(po)
        opening = stock
        inbound = sum(po["qty"] for po in pipeline.get(day, []))
        observed = series.get(day, 0)
        supplied = min(observed, opening + inbound)
        closing = opening + inbound - supplied
        ledger.append({"date": day, "opening": opening, "inbound": inbound, "observed": observed,
                       "supplied": supplied, "shortfall": observed - supplied, "closing": closing})
        stock = closing
    return ledger, orders


def build_policy(sku: str, product: dict, name: str, stats: dict, scenario: str) -> dict:
    lead = LEAD_TIME.get(product["category"], DEFAULT_LEAD_TIME)
    reorderable = scenario not in {"summer_clearance_scenario", "winter_carryover_scenario"}
    no_order_after = None
    if scenario == "summer_clearance_scenario":
        no_order_after = date(2020, 7, 31)       # 재발주 불가 설정일 2020-08-01
    elif scenario == "winter_carryover_scenario":
        no_order_after = date(2020, 6, 30)       # 기간 시작 전부터 재발주 불가
    return {"sku": sku, "lead_time": lead, "reorderable": reorderable, "first": stats["first"],
            "no_order_after": no_order_after, "bucket": name, "scenario": scenario}


def initial_state(policy: dict, series: dict[date, int], presale_qty: int) -> dict:
    """07-01 기초재고 또는 초도 입고. 기준일까지의 관측 판매만 사용한다."""
    first, lead = policy["first"], policy["lead_time"]
    if first is None:
        receipt = PRESALE_RECEIPT
        return {"opening": 0, "pos": [{"order": receipt - timedelta(lead), "receipt": receipt,
                                       "qty": presale_qty, "kind": "initial"}]}
    if first >= LEDGER_START:
        receipt = first - timedelta(2)
        qty = max(MOQ, round_pack(window(series, first, min(AS_OF, first + timedelta(lead + 6)))))
        return {"opening": 0, "pos": [{"order": receipt - timedelta(lead), "receipt": receipt,
                                       "qty": qty, "kind": "initial"}]}
    rate = trailing_rate(series, LEDGER_START, first)
    cover = {"summer_clearance_scenario": 75, "winter_carryover_scenario": 0}.get(policy["scenario"], lead + 14)
    if policy["scenario"] == "winter_carryover_scenario":
        # 작년 겨울 잔여 고정 물량: 7~8월 관측 판매의 2배 또는 40개 중 큰 값 (가정)
        return {"opening": max(40, round_pack(2 * window(series, LEDGER_START, AS_OF))), "pos": []}
    if policy["bucket"] == "low_sales":
        return {"opening": max(MOQ, round_pack(rate * cover)), "pos": []}
    return {"opening": round_pack(rate * cover), "pos": []}


def repair_until_as_of(policy, series, initial):
    """07-01~08-31 구간에 공급 부족분이 생기면 기초(또는 초도) 수량을 늘린다. 9월 판매는 보지 않는다.

    기준일까지는 관측 판매를 모두 공급할 수 있어야 한다(관측된 판매는 실제로 일어났기 때문).
    재발주 불가 상품은 기준일 재고가 최근 14일 평균 × 남은 수불 기간 × 1.5 이상이 되게 한다.
    더 받을 수 없는 상품을 기준일에 0개로 만들지 않기 위한 규칙이며, 기준일까지의 판매만 쓴다.
    """
    end_floor = 0
    if not policy["reorderable"]:
        rate14 = window(series, AS_OF - timedelta(13), AS_OF) / 14
        end_floor = ceil(rate14 * (LEDGER_END - AS_OF).days * NON_REORDER_BUFFER)
    for _ in range(50):
        ledger, orders = simulate(policy, series, initial)
        deficit = sum(row["shortfall"] for row in ledger if row["date"] <= AS_OF)
        as_of_stock = next(row["closing"] for row in ledger if row["date"] == AS_OF)
        deficit = max(deficit, end_floor - as_of_stock)
        if deficit <= 0:
            return initial, ledger, orders
        if initial["pos"] and initial["opening"] == 0:
            initial["pos"][0]["qty"] += round_pack(deficit)
        else:
            initial["opening"] += round_pack(deficit)
        initial["repaired"] = True
    raise RuntimeError(f"{policy['sku']}: 기준일 전 재고 정합 실패")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()

    rng = random.Random(SEED)
    products, sales = load(args.db)
    chosen = select(products, sales, rng)

    # 기준일까지 판매가 없는 상품의 초도 수량: 7월 이후 처음 관측된 상품들이 첫 28일 동안 판 수량의 섹션별 중앙값
    analog: dict[str, list[int]] = defaultdict(list)
    for sku, product in products.items():
        stats = profile(sales.get(sku, {}))
        if stats["first"] and LEDGER_START <= stats["first"] <= AS_OF - timedelta(27):
            analog[product["section"]].append(window(sales[sku], stats["first"], stats["first"] + timedelta(27)))

    policies, ledgers, purchase_orders, economics = [], [], [], []
    po_seq = 0
    for sku, name, stats in chosen:
        product, series = products[sku], sales.get(sku, {})
        scenario, scenario_reason = lifecycle(product, name, stats)
        policy = build_policy(sku, product, name, stats, scenario)
        presale_qty = round_pack(median(analog[product["section"]])) if analog[product["section"]] else 100
        initial, _, _ = repair_until_as_of(policy, series, initial_state(policy, series, presale_qty))
        ledger, orders = simulate(policy, series, initial)

        for row in ledger:
            ledgers.append({"sku": sku, "date": row["date"].isoformat(),
                            "period": "as_of_window" if row["date"] <= AS_OF else "post_as_of_observed",
                            "opening_stock_synthetic": row["opening"],
                            "inbound_units_synthetic": row["inbound"],
                            "units_sold_observed": row["observed"],
                            "units_supplied_synthetic": row["supplied"],
                            "supply_shortfall_synthetic": row["shortfall"],
                            "closing_stock_synthetic": row["closing"],
                            "sales_source": "hm_observed",
                            "inventory_source": "synthetic_policy_v2"})

        for po in sorted(orders, key=lambda item: (item["receipt"], item["kind"])):
            po_seq += 1
            received = po["receipt"] <= LEDGER_END
            reason = {
                "initial": "기준일까지 판매 미관측 상품의 초도 입고: 같은 섹션 신규 관측 상품의 첫 28일 판매 중앙값" if stats["first"] is None
                else "처음 관측된 판매일 2일 전 초도 입고: 첫 (리드타임+7)일 관측 판매 이상, 최소 30개",
                "policy": f"월요일 검토 · 전날까지 28일 평균 × (리드타임 {policy['lead_time']} + 7 + 안전 7일) − (재고+미입고), 최소 30개·10개 단위",
            }[po["kind"]]
            if initial.get("repaired") and po["kind"] == "initial":
                reason += " · 기준일까지 관측 판매를 모두 공급하도록 수량 보정"
            purchase_orders.append({
                "po_id": f"HMPO-{po_seq:04d}", "sku": sku,
                "order_date_assumed": po["order"].isoformat(),
                "expected_receipt_date_assumed": po["receipt"].isoformat(),
                "actual_receipt_date_assumed": po["receipt"].isoformat() if received else "",
                "ordered_units_synthetic": po["qty"],
                "received_units_synthetic": po["qty"] if received else 0,
                "status": "received" if received else "open", "assumption_reason": reason})

        assumption = [f"리드타임 {policy['lead_time']}일은 상품 종류별 가정"]
        if not policy["reorderable"]:
            setting = (policy["no_order_after"] + timedelta(1)).isoformat()
            assumption.append(f"재발주 불가 설정일={setting}")
        if stats["first"] is not None and stats["first"] < LEDGER_START:
            assumption.append("07-01 기초재고는 전날까지 28일 평균 판매 기준 가정")
        if initial.get("repaired"):
            assumption.append("기준일까지 관측 판매를 모두 공급하도록 기초·초도 수량 보정")
        policies.append({
            "sku": sku, "name": product["name"], "section": product["section"], "category": product["category"],
            "observed_first_sale_date": stats["first"].isoformat() if stats["first"] else "",
            "scenario_lifecycle": scenario,
            "reorderable_assumed": str(policy["reorderable"]).lower(),
            "lead_time_days_assumed": policy["lead_time"],
            "selection_reason": f"{name}: 최근14일 {stats['u14']} / 직전14일 {stats['p14']} / 30일 {stats['u30']} (2020-08-31까지 관측) · {scenario_reason}",
            "assumption_reason": " · ".join(assumption)})

        list_price = LIST_PRICE[product["category"]]
        cost = int(round(list_price * COST_RATIO / 100) * 100)
        tier_rule = f"category={product['category']} → 정가 {list_price}원 (가정 등급표)"
        cost_rule = f"정가 × {COST_RATIO:.2f}, 100원 단위 (가정)"
        segments = [(LEDGER_START, LEDGER_END, list_price)]
        if scenario == "summer_clearance_scenario":
            start, rate = SUMMER_MARKDOWN
            segments = [(LEDGER_START, start - timedelta(1), list_price),
                        (start, LEDGER_END, int(round(list_price * (1 - rate) / 100) * 100))]
        elif scenario == "winter_carryover_scenario":
            segments = [(LEDGER_START, LEDGER_END, int(round(list_price * (1 - CARRYOVER_DISCOUNT) / 100) * 100))]
        for start, end, selling in segments:
            economics.append({"sku": sku, "valid_from": start.isoformat(), "valid_to": end.isoformat(),
                              "list_price_krw_assumed": list_price, "selling_price_krw_assumed": selling,
                              "unit_cost_krw_assumed": cost, "price_tier_rule": tier_rule,
                              "cost_rule": cost_rule, "source_label": "simulation_assumption"})

    args.out.mkdir(parents=True, exist_ok=True)
    write(args.out / "hm_product_policy.csv", policies)
    write(args.out / "hm_inventory_ledger.csv", ledgers)
    write(args.out / "hm_purchase_orders.csv", purchase_orders)
    write(args.out / "hm_economics.csv", economics)
    counts = defaultdict(int)
    for _, name, _ in chosen:
        counts[name] += 1
    print(f"선정 {len(chosen)}종 {dict(counts)} · 수불 {len(ledgers)}행 · 발주 {len(purchase_orders)}행 · 가격 {len(economics)}행")
    post = [row for row in ledgers if row["period"] == "post_as_of_observed"]
    observed = sum(row["units_sold_observed"] for row in post)
    shortfall = sum(row["supply_shortfall_synthetic"] for row in post)
    print(f"9/1~9/22 관측 판매 {observed}개 · 가상 공급 {observed - shortfall}개 · 가상 정책상 공급 부족분 {shortfall}개 "
          f"({len({row['sku'] for row in post if row['supply_shortfall_synthetic']})}종)")


def write(path: Path, rows: list[dict]):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
