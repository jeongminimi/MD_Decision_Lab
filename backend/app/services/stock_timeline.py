"""Day-by-day stock check for an assumed sales quantity, so a later receipt cannot hide an earlier stock gap."""

from datetime import date, timedelta
from math import ceil

HORIZON_DAYS = 30
EVEN_SPREAD_NOTE = ("예상 판매량을 30일에 고르게 나눠 날짜별로 재고를 확인했습니다. "
                    "입고일 당일부터 판매 가능하다고 봅니다. 실제 판매는 날짜별로 몰릴 수 있습니다.")


def check_daily_availability(as_of: date, stock: int, receipts: list[tuple[date, int]],
                             expected_units: int, horizon: int = HORIZON_DAYS) -> dict:
    """Cumulative demand on day d is expected × d / horizon; receipts after the horizon are ignored.

    Returns feasibility plus the first day stock runs short and the largest cumulative gap (rounded up)."""
    end = as_of + timedelta(horizon)
    counted = sorted((day, units) for day, units in receipts if day <= end and units > 0)
    first_gap, max_gap = None, 0
    for offset in range(1, horizon + 1):
        day = as_of + timedelta(offset)
        supply = stock + sum(units for arrival, units in counted if arrival <= day)
        # Compare in integers: expected × d / horizon > supply  ⇔  expected × d > supply × horizon.
        if expected_units * offset > supply * horizon:
            first_gap = first_gap or day
            max_gap = max(max_gap, ceil(expected_units * offset / horizon - supply))
    total = stock + sum(units for _, units in counted)
    return {"feasible": first_gap is None, "available_units": total, "first_gap_date": first_gap,
            "max_gap_units": max_gap if first_gap else 0,
            "receipts_counted": [{"date": day, "units": units} for day, units in counted]}
