"""Sell-through = units sold ÷ (opening stock + units received), only when the stock ledger closes."""

DEFINITION = ("판매율 = 기간 판매 수량 ÷ (기초재고 + 기간 입고). 기초재고는 시작일 판매 전 수량, "
              "기말재고는 기준일 판매 후 수량입니다.")


def sell_through(*, opening: int | None, received: int | None, sold: int, closing: int | None) -> dict:
    """Returns status 'ok', 'missing', 'mismatch' or 'no_supply'; pct is set only for 'ok'.

    A ledger that does not close (opening + received − sold ≠ closing) means returns, losses or transfers
    are unrecorded, so the ratio would not describe the period and is withheld."""
    base = {"pct": None, "sold_units": sold, "opening_stock": opening, "received_units": received,
            "closing_stock": closing, "difference_units": None}
    if opening is None or received is None or closing is None:
        return {**base, "status": "missing", "reason": "기초재고·기간 입고·기말재고가 모두 있어야 계산합니다."}
    difference = closing - (opening + received - sold)
    if difference:
        return {**base, "status": "mismatch", "difference_units": difference,
                "reason": (f"기초재고 + 입고 − 판매와 기말재고가 {difference:+d}개 다릅니다. "
                           "반품·손실·이동 기록을 확인하기 전에는 판매율을 계산하지 않습니다.")}
    if opening + received == 0:
        return {**base, "status": "no_supply", "reason": "기간 중 판매할 수 있는 재고가 없었습니다."}
    return {**base, "status": "ok", "pct": round(sold / (opening + received) * 100, 1), "reason": DEFINITION}
