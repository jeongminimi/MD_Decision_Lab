from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DailySale, MDAction


def evaluate_action(action: MDAction, db: Session, as_of: date | None = None) -> dict:
    """Descriptive 7-day comparison, never an attribution of causality."""
    seoul = timezone(timedelta(hours=9))
    as_of = as_of or datetime.now(seoul).date()
    action_date = action.completed_at.replace(tzinfo=timezone.utc).astimezone(seoul).date() if action.completed_at else None
    result = {
        "action_id": action.id,
        "status": "planned",
        "interpretation": "실행 완료 표시 후 전후 7일 판매자료가 모이면 비교합니다. 변화가 조치의 효과를 증명하지는 않습니다.",
        "action_date": action_date,
        "before": None,
        "after": None,
        "stock_at_log": action.stock_before,
        "stock_now": action.product.stock_on_hand,
        "stock_note": "현재고는 조회 시점 값이며 조치 완료일의 재고 스냅샷이 아닙니다.",
        "missing_before_days": 7,
        "missing_after_days": 7,
    }
    if action.completed_at is None:
        return result

    assert action_date is not None
    before_start, before_end = action_date - timedelta(days=7), action_date - timedelta(days=1)
    after_start, after_end = action_date + timedelta(days=1), action_date + timedelta(days=7)
    rows = db.scalars(select(DailySale).where(
        DailySale.product_id == action.product_id,
        DailySale.sale_date.between(before_start, after_end),
    )).all()
    before_rows = [row for row in rows if before_start <= row.sale_date <= before_end]
    after_rows = [row for row in rows if after_start <= row.sale_date <= after_end]
    result["missing_before_days"] = 7 - len({row.sale_date for row in before_rows})
    result["missing_after_days"] = 7 - len({row.sale_date for row in after_rows})
    result["before_period"] = {"start": before_start, "end": before_end}
    result["after_period"] = {"start": after_start, "end": after_end}

    if as_of < after_end or result["missing_before_days"] or result["missing_after_days"]:
        result["status"] = "waiting_for_data"
        result["interpretation"] = (
            "완료 표시일 전후의 7일씩을 비교하려면 두 기간 모두 일별 판매행 7개가 필요합니다. "
            "판매 0건인 날도 0개로 입력하세요. 자료가 완전하지 않으면 변화율을 표시하지 않습니다."
        )
        return result

    def metrics(period_rows):
        margin_complete = all(row.gross_margin is not None for row in period_rows)
        return {
            "units": sum(row.units_sold for row in period_rows),
            "revenue": round(sum(row.revenue for row in period_rows), 2),
            "gross_margin": round(sum(row.gross_margin for row in period_rows), 2) if margin_complete else None,
        }

    result["status"] = "comparable"
    result["before"] = metrics(before_rows)
    result["after"] = metrics(after_rows)
    result["interpretation"] = (
        "같은 길이의 완료 표시일 전후 7일을 기술적으로 비교한 값입니다. "
        "가격·광고·시즌·경쟁사 등 외부 요인을 통제하지 않았으므로 조치의 인과 효과가 아닙니다."
    )
    return result
