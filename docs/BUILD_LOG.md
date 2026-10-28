# Build log

## Day 1 — 2026-10-27

- Named the portfolio project `MD_Decision_Lab`.
- Defined a relational data model for products, dated sales, and MD action history.
- Added synthetic apparel data and explainable stock/replenishment/overstock rules.
- Added a CSV import path and API endpoints for the dashboard, product analysis, and action log.
- Added separate product/inventory and dated-sales CSV imports. Catalog import upserts SKUs and does not delete omitted products or their histories.

## Day 2 — planned

- Review and refine the interface against the API behavior.
- Review both import templates and improve row-level validation feedback.
- Walk through the full demo scenario and capture a portfolio-ready explanation of assumptions, limits, and observed behavior.

## Claims and evidence

- The included data is synthetic; it demonstrates how the rules behave and is not evidence of actual sales lift.
- Recommendations are decision support. The prototype does not place orders, change prices, or publish content.

## Analysis and content workflow extension — 2026-10-27

- Added a conditional 7-day demand signal, low-sample warnings, and a hold on replenishment when recent sales are zero. Exported observed demand, assumed stock/cost, and recommendation reasoning as CSV.
- Added a descriptive pre/post action view requiring seven daily rows on each side of the completion date, including explicit zero-sale rows. Missing data blocks the comparison; current stock is labelled separately.

## Editorial UI redesign — 2026-10-27

- Used the Superpowers brainstorming, planning, inline implementation, and verification guidance with an owner-provided wellness UI image as a visual reference. The image was copied to `docs/references/` and the design decision is recorded in `docs/superpowers/`.
- React TypeScript check, CSS parsing, and the eight backend tests pass. The local Vite start still fails with esbuild `spawn EPERM` in this Codex shell, so a visual check in Antigravity is required before claiming the final layout is finished.
- Review fixes: kept sidebar labels on one line; and explained that a product with 30-day sales but zero sales in the last seven days needs demand review before replenishment.
