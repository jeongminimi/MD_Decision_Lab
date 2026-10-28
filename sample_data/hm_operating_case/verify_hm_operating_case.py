"""hm_operating_case 산출물 전수 검증. DB는 읽기 전용으로만 연다.

실행 (MD_Decision_Lab/ 에서):
    python sample_data/hm_operating_case/verify_hm_operating_case.py
"""

import csv
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_hm_operating_case as gen  # noqa: E402

AS_OF, START, END = gen.AS_OF, gen.LEDGER_START, gen.LEDGER_END
failures: list[str] = []


def check(condition: bool, message: str):
    if not condition:
        failures.append(message)


def read(name: str) -> list[dict[str, str]]:
    # 모든 값을 문자열로 읽는다. article_id를 숫자로 바꾸면 앞자리 0이 사라진다.
    with (HERE / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    policy, ledger = read("hm_product_policy.csv"), read("hm_inventory_ledger.csv")
    orders, economics = read("hm_purchase_orders.csv"), read("hm_economics.csv")

    con = sqlite3.connect(f"file:{gen.DEFAULT_DB.as_posix()}?mode=ro", uri=True)
    db_skus = {sku for (sku,) in con.execute(
        "SELECT p.sku FROM work_products p JOIN work_datasets d ON d.id=p.dataset_id WHERE d.kind='hm'")}
    observed: dict[tuple[str, date], int] = defaultdict(int)
    for sku, day, units in con.execute(
            "SELECT p.sku, s.sale_date, SUM(s.units) FROM work_daily_sales s JOIN work_products p ON p.id=s.product_id "
            "JOIN work_datasets d ON d.id=p.dataset_id WHERE d.kind='hm' GROUP BY p.sku, s.sale_date"):
        observed[(sku, date.fromisoformat(day))] += units
    con.close()

    # 1. SKU 연결
    skus = [row["sku"] for row in policy]
    check(len(skus) == len(set(skus)), "정책 파일 SKU 중복")
    check(40 <= len(skus) <= 60, f"선정 상품 수 {len(skus)}")
    check(all(re.fullmatch(r"\d{10}", sku) for sku in skus), "10자리 숫자 문자열이 아닌 SKU")
    check(set(skus) <= db_skus, f"DB에 없는 SKU {set(skus) - db_skus}")
    leading_zero = sum(sku.startswith("0") for sku in skus)
    as_int = {str(int(sku)) for sku in skus}
    check(not (as_int & set(skus)) or leading_zero == 0, "정수 변환 SKU가 원래 SKU와 섞임")
    for name, rows in (("수불", ledger), ("가격", economics)):
        check({row["sku"] for row in rows} == set(skus), f"{name} 파일 SKU 집합이 정책 파일과 다름")
    check({row["sku"] for row in orders} <= set(skus), "발주 파일에 정책 파일 밖 SKU")  # 기초재고만 있는 상품은 발주가 없을 수 있음

    # 2. 첫 관측 판매일 (기준일까지)
    for row in policy:
        days = [d for (s, d), u in observed.items() if s == row["sku"] and u > 0 and d <= AS_OF]
        expected = min(days).isoformat() if days else ""
        check(row["observed_first_sale_date"] == expected, f"{row['sku']} 첫 관측 판매일 불일치")

    # 3. 재고 수불 전수 검사
    by_sku: dict[str, list[dict]] = defaultdict(list)
    for row in ledger:
        by_sku[row["sku"]].append(row)
    expected_days = [START + timedelta(i) for i in range((END - START).days + 1)]
    for sku, rows in by_sku.items():
        check([date.fromisoformat(r["date"]) for r in rows] == expected_days, f"{sku} 날짜 연속성 오류")
        previous = None
        for r in rows:
            o, i, s, sup, short, c = (int(r[k]) for k in (
                "opening_stock_synthetic", "inbound_units_synthetic", "units_sold_observed",
                "units_supplied_synthetic", "supply_shortfall_synthetic", "closing_stock_synthetic"))
            day = date.fromisoformat(r["date"])
            check(sup == min(s, o + i), f"{sku} {day} 공급 가능 수량 계산 오류")
            check(short == s - sup, f"{sku} {day} 공급 부족분 계산 오류")
            check(o + i - sup == c, f"{sku} {day} 수불식 불일치")
            check(min(o, i, c, short) >= 0, f"{sku} {day} 음수 재고·입고·부족분")
            check(day > AS_OF or short == 0, f"{sku} {day} 기준일 이전 공급 부족분")
            check(r["period"] == ("as_of_window" if day <= AS_OF else "post_as_of_observed"), f"{sku} {day} 기간 구분 오류")
            check(s == observed.get((sku, day), 0), f"{sku} {day} 판매가 DB 관측값과 다름")
            check(previous is None or o == previous, f"{sku} {day} 전일 기말과 기초 불일치")
            previous = c

    # 4. 발주 ↔ 수불 입고
    receipts: Counter = Counter()
    po_ids = [row["po_id"] for row in orders]
    check(len(po_ids) == len(set(po_ids)), "po_id 중복")
    for row in orders:
        ordered, received = int(row["ordered_units_synthetic"]), int(row["received_units_synthetic"])
        check(received <= ordered, f"{row['po_id']} 입고 > 발주")
        check(row["status"] in {"received", "open"}, f"{row['po_id']} 허용되지 않는 상태 {row['status']}")
        check(bool(row["order_date_assumed"]) and date.fromisoformat(row["order_date_assumed"]) <= AS_OF,
              f"{row['po_id']} 발주일 없음 또는 기준일 이후 발주")
        if row["status"] == "open":
            check(received == 0 and not row["actual_receipt_date_assumed"]
                  and date.fromisoformat(row["expected_receipt_date_assumed"]) > END, f"{row['po_id']} 미입고 상태 오류")
        else:
            receipts[(row["sku"], row["actual_receipt_date_assumed"])] += received
    ledger_inbound = Counter({(r["sku"], r["date"]): int(r["inbound_units_synthetic"])
                              for r in ledger if int(r["inbound_units_synthetic"])})
    check(+receipts == ledger_inbound, "발주 입고와 수불 입고가 일치하지 않음")

    # 5. 재발주 불가 상품: 설정일 이후 신규 발주 없음
    settings = {}
    for row in policy:
        if row["reorderable_assumed"] == "false":
            match = re.search(r"재발주 불가 설정일=(\d{4}-\d{2}-\d{2})", row["assumption_reason"])
            check(match is not None, f"{row['sku']} 재발주 불가 설정일 누락")
            if match:
                settings[row["sku"]] = date.fromisoformat(match.group(1))
    for row in orders:
        if row["sku"] in settings:
            check(bool(row["order_date_assumed"]) and date.fromisoformat(row["order_date_assumed"]) < settings[row["sku"]],
                  f"{row['po_id']} 재발주 불가 설정일 이후 발주")

    # 6. 가격 구간
    segments: dict[str, list] = defaultdict(list)
    for row in economics:
        segments[row["sku"]].append(row)
        lp, sp, uc = (float(row[k]) for k in ("list_price_krw_assumed", "selling_price_krw_assumed", "unit_cost_krw_assumed"))
        check(0 < uc < sp <= lp, f"{row['sku']} 가격·원가 관계 오류")
        check(row["source_label"] == "simulation_assumption", f"{row['sku']} 출처 표시 누락")
    for sku, rows in segments.items():
        rows.sort(key=lambda r: r["valid_from"])
        check(rows[0]["valid_from"] == START.isoformat() and rows[-1]["valid_to"] == END.isoformat(), f"{sku} 가격 기간 범위")
        for a, b in zip(rows, rows[1:]):
            check(date.fromisoformat(a["valid_to"]) + timedelta(1) == date.fromisoformat(b["valid_from"]), f"{sku} 가격 구간 공백·중복")

    # 7. 9월 정보 누출 검사: 9월 판매를 지우고 다시 만들어도 선정과 8/31 상태가 같아야 한다.
    original_load = gen.load

    def load_without_september(db_path):
        products, sales = original_load(db_path)
        for series in sales.values():
            for day in [d for d in series if d > AS_OF]:
                del series[day]
        return products, sales

    gen.load = load_without_september
    leak_dir = Path(gen.__file__).parent / "_leak_check_tmp"
    sys.argv = [sys.argv[0], "--out", str(leak_dir)]
    try:
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            gen.main()
        leak_ledger = {(r["sku"], r["date"]): r for r in csv.DictReader((leak_dir / "hm_inventory_ledger.csv").open(encoding="utf-8-sig"))}
        leak_orders = [r for r in csv.DictReader((leak_dir / "hm_purchase_orders.csv").open(encoding="utf-8-sig"))]
        leak_policy = [r["sku"] for r in csv.DictReader((leak_dir / "hm_product_policy.csv").open(encoding="utf-8-sig"))]
    finally:
        gen.load = original_load
        for path in leak_dir.glob("*"):
            path.unlink()
        leak_dir.rmdir()
    check(leak_policy == skus, "9월 판매 유무에 따라 선정 상품이 달라짐")
    for r in ledger:
        if date.fromisoformat(r["date"]) <= AS_OF:
            other = leak_ledger[(r["sku"], r["date"])]
            check(r["closing_stock_synthetic"] == other["closing_stock_synthetic"]
                  and r["inbound_units_synthetic"] == other["inbound_units_synthetic"], f"{r['sku']} {r['date']} 8/31 이전 상태가 9월 판매에 의존")

    def as_of_orders(rows):
        return sorted((r["sku"], r["order_date_assumed"], r["expected_receipt_date_assumed"], r["ordered_units_synthetic"])
                      for r in rows if r["order_date_assumed"] and date.fromisoformat(r["order_date_assumed"]) <= AS_OF)
    check(as_of_orders(orders) == as_of_orders(leak_orders), "8/31까지의 발주가 9월 판매에 의존")

    # 8. 기준일 판단 (backend/app/services/work_risk.py와 같은 규칙: 판매 미관측 → 재고 → 판매 변화)
    closing = {(r["sku"], r["date"]): int(r["closing_stock_synthetic"]) for r in ledger}
    shortfall = Counter()
    for r in ledger:
        shortfall[r["sku"]] += int(r["supply_shortfall_synthetic"])
    lead = {row["sku"]: int(row["lead_time_days_assumed"]) for row in policy}
    names = {row["sku"]: row for row in policy}
    judgments = []
    for sku in skus:
        units = lambda a, b: sum(observed.get((sku, a + timedelta(i)), 0) for i in range((b - a).days + 1))
        u14, p14 = units(AS_OF - timedelta(13), AS_OF), units(AS_OF - timedelta(27), AS_OF - timedelta(14))
        stock = closing[(sku, AS_OF.isoformat())]
        rate = u14 / 14                      # H&M 작업공간은 2019-01-01부터라 data_days ≥ 28
        cover = round(stock / rate, 1) if rate > 0 else None
        if not names[sku]["observed_first_sale_date"]:
            risk = "not_observed"
        elif stock == 0:
            risk = "stockout"
        elif cover is not None and cover <= lead[sku]:
            risk = "stock_risk"
        elif cover is not None and cover >= 60:
            risk = "overstock"
        elif p14 >= 5 and u14 <= p14 * 0.7:
            risk = "declining"
        elif u14 >= 5 and u14 >= max(1, p14) * 1.3:
            risk = "rising"
        else:
            risk = "stable"
        september = units(AS_OF + timedelta(1), END)
        judgments.append((risk, sku, u14, p14, stock, cover, lead[sku], september, shortfall[sku]))

    print("== 전수 검증 ==")
    print(f"선정 {len(skus)}종 · 앞자리 0 SKU {leading_zero}종 (정수로 읽으면 {leading_zero}종 모두 DB와 연결 실패)")
    print(f"수불 {len(ledger)}행 · 발주 {len(orders)}행 · 가격 {len(economics)}행")
    print(f"발주 상태 {dict(Counter(r['status'] for r in orders))}")
    print(f"실패 {len(failures)}건")
    for message in failures[:20]:
        print("  -", message)
    print("\n== 2020-08-31 판단 (work_routes 규칙) ==")
    print(dict(Counter(j[0] for j in judgments)))
    for risk in ("not_observed", "stockout", "stock_risk", "overstock", "declining", "rising", "stable"):
        rows = sorted((j for j in judgments if j[0] == risk), key=lambda j: -j[2])
        for j in rows[:3]:
            p = names[j[1]]
            print(f"{risk:10s} {j[1]} {p['name'][:22]:22s} {p['scenario_lifecycle']:26s} 최근14일 {j[2]:>5} 직전14일 {j[3]:>5} "
                  f"재고 {j[4]:>5} 소진예상 {j[5]} 리드 {j[6]} | 9월 관측 {j[7]} 공급 부족분 {j[8]}")
    post = [r for r in ledger if r["period"] == "post_as_of_observed"]
    post_observed = sum(int(r["units_sold_observed"]) for r in post)
    post_short = sum(int(r["supply_shortfall_synthetic"]) for r in post)
    print(f"\n== 9/1~9/22 이후 관측 ==\n관측 판매 {post_observed}개 · 가상 공급 {post_observed - post_short}개 · "
          f"가상 정책상 공급 부족분 {post_short}개 ({post_short / post_observed:.1%})")
    for risk in sorted({j[0] for j in judgments}):
        group = [j for j in judgments if j[0] == risk]
        print(f"{risk}: 부족 발생 {sum(j[8] > 0 for j in group)} / {len(group)}종 · 부족분 {sum(j[8] for j in group)}개")
    pre = [j for j in judgments if not names[j[1]]["observed_first_sale_date"]]
    print("판매 미관측 상품:", [(j[1], j[4], j[7], j[8]) for j in pre])

    # 시뮬레이션 매출총이익 (7~8월, 가정 가격)
    price = {}
    for row in economics:
        price.setdefault(row["sku"], []).append(row)
    total_rev = total_gp = 0.0
    for (sku, day), units in observed.items():
        if sku in price and START <= day <= AS_OF:
            seg = next(r for r in price[sku] if r["valid_from"] <= day.isoformat() <= r["valid_to"])
            total_rev += units * float(seg["selling_price_krw_assumed"])
            total_gp += units * (float(seg["selling_price_krw_assumed"]) - float(seg["unit_cost_krw_assumed"]))
    print(f"\n시뮬레이션 7~8월 매출 {total_rev:,.0f}원 · 매출총이익 {total_gp:,.0f}원 (실제 H&M 값 아님)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
