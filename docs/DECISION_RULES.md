# Decision rules — MVP v2

These are explicit heuristics for a small demonstrator, not a forecast model. Thresholds should be configurable after a real MD validates them.

## Metrics

- `units_30d`: units sold in the last 30 days.
- `avg_daily_units`: `units_30d / 30`.
- `avg_daily_7d`: `units_7d / 7`.
- `decision_daily_units`: use the 7-day rate only when 30-day units >= 10, 7-day units >= 5, sales occurred on at least 3 days in the 30-day window, and the two rates differ by at least 30%. Otherwise use the 30-day rate. These are transparent trial thresholds, not a validated forecast.
- `available_units`: `stock_on_hand + inbound_units`.
- `days_of_cover`: `stock_on_hand / decision_daily_units`; undefined when there were no sales.
- `cover_including_inbound`: `(stock_on_hand + inbound_units) / decision_daily_units`.
- `estimated_revenue_30d`: sum of imported sales revenue in the last 30 days.
- `estimated_gross_margin_30d`: imported gross margin when present; otherwise revenue less unit cost times sold quantity. Label as an estimate when calculated.

## Risk precedence

1. `out_of_stock`: current stock is zero or below.
2. `data_insufficient`: no sales in the lookback period, or at least 10 units in 30 days followed by fewer than 5 units in 7 days with a rate drop greater than 30%. In the latter case, investigate a promotion ending, stock availability, exposure, and missing records before replenishing.
3. `stockout_risk`: stock cover is at or below the product lead time.
4. `overstock_risk`: stock plus inbound cover exceeds the product target cover by more than 30 days.
5. `slow_moving`: stock cover exceeds the product's configured target cover, while it has non-zero sales history.
6. `healthy`: none of the above.

For an Olist inventory scenario, a product with no delivered sales in the complete selected 30-day historical window is not treated as an urgent stockout. Positive assumed stock is marked slow-moving; zero assumed stock is marked as requiring data review. No replenishment quantity is suggested without observed demand.

## Suggested next action

- `out_of_stock` or `stockout_risk`: review replenishment and confirm supplier availability. Suggest quantity only when target cover, inbound, and lead time are present.
- `overstock_risk`: review a promotion or live exposure; do not auto-discount.
- `slow_moving`: inspect product page, audience fit, and a small exposure test.
- `data_insufficient`: collect enough sales history before making a demand recommendation.
- `healthy`: monitor; no intervention required.

The UI must show the values that triggered each suggestion and retain the human decision separately from the system recommendation.

Warnings flag fewer than 10 units in 30 days, sales on fewer than 3 days, a 7-day trend used for the decision, or a large recent decline with fewer than 5 recent sales. Suggested replenishment is withheld if 30-day units are below 10, sales happened on fewer than 3 days, or the recent decline requires investigation. Otherwise it uses `ceil(target cover days × decision daily units - stock - inbound)`, floored at zero; it is a review quantity, not an order. The scenario CSV export repeats observed demand and assumed inventory/cost in distinct columns.
