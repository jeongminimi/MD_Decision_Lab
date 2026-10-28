# MD portfolio direction

## Purpose

Show how an apparel MD uses sales, cost, and stock to compare two possible actions before deciding. The owner contributed the field problem, workflow, decision criteria, AI-assisted build direction, and result review. The application must not claim proven sales lift.

## Main flow

1. Open the apparel case directly. State that its data is synthetic and fixed at 2026-08-31.
2. Choose a product and read the measured sales, assumed snapshot stock, cost, and recommendation evidence.
3. Enter two action assumptions: discount, expected 30-day units, and additional purchase quantity.
4. Compare estimated revenue, gross profit, remaining stock, and purchase cash commitment. Flag impossible or unsupported assumptions.
5. Record the MD's own decision and reason. Do not represent the comparison as a randomized A/B test or an observed outcome.

## Boundaries

- The old seeded demo stays available as a secondary legacy workspace until its data can be migrated or retired safely.
- The comparison is deterministic arithmetic. No external AI API is required or used.
- Cost of goods is deducted from sold units to calculate gross profit; purchase cash commitment is shown separately. Fees, returns, advertising, and taxes are missing, so there is no net-profit claim.
- Do not change the existing SQLite schema or rewrite historical sales.

## Acceptance checks

- A valid two-option comparison returns reproducible arithmetic without mutating products or sales.
- Reorder-disabled items reject additional purchase assumptions.
- Expected units beyond available stock are flagged, not silently converted into sales.
- Invalid negative/non-finite inputs fail validation.
