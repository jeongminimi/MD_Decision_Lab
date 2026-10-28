from datetime import date, timedelta
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DailySale, MerchandisingContext, Product
from ..schemas import ProductAnalysis


RISK_LABELS = {
    "out_of_stock": "재고 소진",
    "data_insufficient": "판매 데이터 부족",
    "stockout_risk": "품절 위험",
    "overstock_risk": "과잉재고 위험",
    "slow_moving": "판매 둔화",
    "healthy": "안정",
}


def analyze_product(product: Product, db: Session, today: date | None = None) -> ProductAnalysis:
    today = today or date.today()
    context = db.get(MerchandisingContext, product.id)
    since = today - timedelta(days=29)
    rows = db.scalars(
        select(DailySale).where(
            DailySale.product_id == product.id,
            DailySale.sale_date >= since,
            DailySale.sale_date <= today,
        )
    ).all()
    units = sum(row.units_sold for row in rows)
    units_7d = sum(row.units_sold for row in rows if row.sale_date >= today - timedelta(days=6))
    sales_days = sum(row.units_sold > 0 for row in rows)
    revenue = round(sum(row.revenue for row in rows), 2)
    margin_present = bool(rows) and all(row.gross_margin is not None or (row.units_sold == 0 and row.revenue == 0) for row in rows)
    unit_cost = product.unit_cost
    stock_on_hand = product.stock_on_hand
    inbound_units = product.inbound_units
    lead_time_days = product.lead_time_days
    target_cover_days = product.target_cover_days
    margin = sum(row.gross_margin if row.gross_margin is not None else row.revenue - row.units_sold * unit_cost for row in rows)
    avg_daily = units / 30
    avg_daily_7d = units_7d / 7
    warnings = []
    if units < 10:
        warnings.append("30일 판매가 10개 미만이라 판매 속도 추정이 불안정합니다.")
    if units and sales_days < 3:
        warnings.append("판매가 발생한 날이 3일 미만이라 단발성 주문의 영향이 큽니다.")
    recent_shift = avg_daily > 0 and abs(avg_daily_7d / avg_daily - 1) >= 0.3
    recent_drop_uncertain = units >= 10 and units_7d < 5 and avg_daily_7d < avg_daily * 0.7
    if recent_drop_uncertain:
        warnings.append("최근 7일 판매가 크게 줄었지만 표본이 5개 미만입니다. 행사 종료·품절·노출 중단·데이터 누락 여부를 확인하세요.")
    replenishment_confident = units >= 10 and sales_days >= 3 and not recent_drop_uncertain
    use_recent = units >= 10 and units_7d >= 5 and sales_days >= 3 and recent_shift
    if use_recent:
        decision_daily = avg_daily_7d
        demand_basis = "7d"
        demand_explanation = "최근 7일 판매가 5개 이상이고 30일 평균과 30% 이상 달라, 최근 7일 속도를 판단에 사용했습니다."
        warnings.append("7일 추세가 일시적일 수 있으므로 행사·품절·대량 주문 여부를 확인하세요.")
    elif units:
        decision_daily = avg_daily
        demand_basis = "30d"
        demand_explanation = "최근 7일 표본 또는 변화폭이 기준에 미치지 않아 30일 평균 판매 속도를 사용했습니다."
    else:
        decision_daily = 0
        demand_basis = "none"
        demand_explanation = "최근 30일 판매가 없어 판매 속도와 재고 커버리지를 계산하지 않았습니다."
    cover = stock_on_hand / decision_daily if decision_daily else None
    total_cover = (stock_on_hand + inbound_units) / decision_daily if decision_daily else None

    if context is not None and context.launch_date is not None and today < context.launch_date:
        risk, rec, reason, replenish = "data_insufficient", "출시 준비 상태 확인", "아직 출시 전이라 판매 속도로 수요나 발주량을 추정하지 않습니다. 초도 물량·입고 일정·노출 계획을 확인하세요.", None
    elif stock_on_hand <= 0:
        risk, rec, reason = "out_of_stock", "재고 확보 가능 여부 확인", "현재 판매 가능한 재고가 0개 이하입니다. 입고 예정 수량과 공급사 일정을 먼저 확인하세요."
        replenish = max(ceil(target_cover_days * decision_daily - inbound_units), 0) if decision_daily and replenishment_confident else None
    elif recent_drop_uncertain:
        risk, rec, reason, replenish = "data_insufficient", "최근 수요 변화 확인", "30일 판매 기록은 있지만 최근 7일 수요가 크게 줄었습니다. 원인을 확인하기 전에는 추가 매입 수량을 제안하지 않습니다.", None
    elif units == 0:
        risk, rec, reason, replenish = "data_insufficient", "판매 데이터 확인", "최근 30일 판매 기록이 없어 수요를 추정할 수 없습니다. 상품 상태와 데이터 누락 여부를 확인하세요.", None
    elif cover is not None and cover <= lead_time_days:
        risk, rec, reason = "stockout_risk", "추가 매입 검토", f"재고 소진 예상은 약 {cover:.1f}일이고 리드타임은 {lead_time_days}일입니다. 입고 시점이 판매 가능 재고보다 늦을 수 있습니다."
        replenish = max(ceil(target_cover_days * decision_daily - stock_on_hand - inbound_units), 0) if replenishment_confident else None
    elif total_cover is not None and total_cover > target_cover_days + 30:
        risk, rec, reason, replenish = "overstock_risk", "프로모션 또는 라이브 노출 검토", f"현재 재고와 입고 예정량은 약 {total_cover:.1f}일 판매분으로 목표 보유일 {target_cover_days}일을 30일 넘게 초과합니다.", None
    elif cover is not None and cover > target_cover_days:
        risk, rec, reason, replenish = "slow_moving", "상품 페이지·노출 테스트 검토", f"현재 재고 커버리지는 약 {cover:.1f}일로 목표 {target_cover_days}일보다 깁니다. 가격 변경 전에 페이지와 노출을 점검하세요.", None
    else:
        risk, rec, reason, replenish = "healthy", "모니터링", "현재 재고 커버리지가 설정한 목표 범위 안에 있습니다.", None

    if context is not None and not context.reorderable:
        replenish = None
        if risk in {"stockout_risk", "out_of_stock"}:
            rec = "잔여 재고 소진·판매 종료 안내 검토"
            reason += " 이 상품은 재발주가 불가능하므로 추가 매입을 제안하지 않습니다. 노출·주문 제한과 품절 안내를 확인하세요."
        elif risk in {"overstock_risk", "slow_moving"}:
            reason += " 재발주 불가 상품이므로 잔여 재고 소진 계획을 검토하세요."
    if context is not None and context.event_start_date is not None and today >= context.event_start_date and demand_basis == "7d":
        warnings.append("최근 7일 판매 속도에 행사 수요가 포함될 수 있습니다. 행사 종료 후에도 같은 속도가 유지된다고 가정하지 마세요.")

    return ProductAnalysis(
        product_id=product.id, sku=product.sku, name=product.name, category=product.category,
        season_group=context.season_group if context else None,
        lifecycle_status=context.lifecycle_status if context else None,
        reorderable=context.reorderable if context else None,
        launch_date=context.launch_date if context else None,
        event_start_date=context.event_start_date if context else None,
        planning_note=context.planning_note if context else None,
        stock_on_hand=stock_on_hand, inbound_units=inbound_units,
        lead_time_days=lead_time_days, target_cover_days=target_cover_days,
        unit_price=product.unit_price, unit_cost=unit_cost, units_7d=units_7d, units_30d=units,
        sales_days_30d=sales_days,
        revenue_30d=revenue, gross_margin_30d=round(margin, 2),
        gross_margin_rate_30d_pct=round(margin / revenue * 100, 1) if revenue > 0 else None,
        unit_markup_pct=round((product.unit_price - unit_cost) / unit_cost * 100, 1) if unit_cost > 0 else None,
        margin_is_estimated=not margin_present,
        avg_daily_units=round(avg_daily, 2), avg_daily_7d=round(avg_daily_7d, 2),
        decision_daily_units=round(decision_daily, 2), demand_basis=demand_basis,
        demand_explanation=demand_explanation, data_warnings=warnings,
        days_of_cover=round(cover, 1) if cover is not None else None,
        cover_including_inbound=round(total_cover, 1) if total_cover is not None else None,
        risk=risk, risk_label="최근 판매 변화 확인" if recent_drop_uncertain and risk == "data_insufficient" else RISK_LABELS[risk], recommendation=rec,
        recommendation_reason=reason,
        suggested_replenishment_units=replenish,
    )
