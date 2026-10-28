"""Shared stock/sales signal rules for the MD workspaces (company, H&M observed, H&M simulation)."""


def classify_work_risk(*, u14: int, p14: int, stock: int | None, cover: float | None,
                       lead_time_days: int | None, reorderable: bool | None,
                       observed_any: bool) -> tuple[str, str, str]:
    """Return (risk, reason, action). Data-completeness checks stay with the caller."""
    if stock == 0:
        return "stockout", "입력한 현재 재고가 0개입니다.", "재고·판매 가능 여부 확인"
    if not observed_any:
        return "not_observed", "기준일까지 관측된 판매가 없습니다. 판매 속도와 소진 예상일을 계산하지 않습니다.", "판매 시작 여부 확인"
    if stock is not None and lead_time_days is not None and cover is not None and cover <= lead_time_days:
        reason = f"재고 {stock}개는 현재 속도로 약 {cover}일분이며, 입고 소요일 {lead_time_days}일 이하입니다."
        return "stock_risk", reason, "재발주 불가: 소진 관리" if reorderable is False else "추가 매입 검토"
    if stock is not None and cover is not None and cover >= 60:
        return "overstock", f"재고 {stock}개는 최근 속도로 약 {cover}일분입니다.", "프로모션·노출 검토"
    if p14 >= 5 and u14 <= p14 * 0.7:
        pct = round((1 - u14 / p14) * 100)
        return "declining", f"최근 2주 판매 {u14}개가 직전 2주 {p14}개보다 {pct}% 줄었습니다.", "재고 확인 후 프로모션 검토"
    if u14 >= 5 and u14 >= max(1, p14) * 1.3:
        return "rising", f"최근 2주 판매 {u14}개가 직전 2주 {p14}개보다 늘었습니다.", "재고·추가 매입 검토"
    return "stable", f"최근 2주 {u14}개, 직전 2주 {p14}개 판매했습니다.", "추이 관찰"


RISK_PRIORITY = {"stockout": 0, "stock_risk": 1, "overstock": 2, "declining": 3, "rising": 4,
                 "not_observed": 5, "data_gap": 6, "stable": 7}
