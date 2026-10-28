# Build log

## Day 1 — 2026-10-27

- Named the portfolio project `MD_Decision_Lab`.
- Defined a relational data model for products, dated sales, and MD action history.
- Added synthetic apparel data and explainable stock/replenishment/overstock rules.
- Added a CSV import path and API endpoints for the dashboard, product analysis, and action log.
- Added separate product/inventory and dated-sales CSV imports. Catalog import upserts SKUs and does not delete omitted products or their histories.
- Started the React dashboard, product analysis drawer, action workflow, and editable short-form draft UI.
- Kept short-form generation behind a small brief/draft contract with no inventory database access, so it can move into a standalone service later.

## Day 2 — planned

- Review and refine the interface against the API behavior.
- Review both import templates and improve row-level validation feedback.
- Walk through the full demo scenario and capture a portfolio-ready explanation of assumptions, limits, and observed behavior.
- Review the short-form boundary for independent reuse.

## Claims and evidence

- The included data is synthetic; it demonstrates how the rules behave and is not evidence of actual sales lift.
- Recommendations are decision support. The prototype does not place orders, change prices, or publish content.
- A future short-form automation should accept a versioned input contract and return draft artifacts; platform-specific publishing credentials and inventory access must remain outside that module.

## Olist extension — 2026-10-27

- Added original Olist `.csv.gz` demand import with a checksum and explicit delivered-order/date/price definitions.
- Added separate inventory simulation scenarios, CSV template and upload, and a historical analysis view in BRL.
- Kept the original apparel demo workspace separate from the Olist scenario view.
- Imported 96,211 delivered orders, 109,880 order items, and 32,081 products from the local Olist source into the SQLite database. A second import returned the existing metadata without duplicating rows.
- Uploaded the five-product synthetic inventory example through the API. It produced stockout, overstock, out-of-stock, and healthy states while the original demo workspace still listed eight products.
- Python files compile and the frontend TypeScript check passes. Vite bundling could not complete in this execution environment because spawning its esbuild helper returned `EPERM`; the remaining browser build check should be run in Antigravity.
- The user opened the app in Antigravity and confirmed that the Olist import and five-product scenario analysis render in the browser.
- Added a same-date, same-product scenario comparison. Under the current 7/30-day decision rules, the two synthetic CSVs show one versus zero stockout-risk products, one versus one overstock-risk products, and R$14,280 versus R$15,500 of assumed stock value. This is a comparison of input assumptions under fixed historical demand.

## Analysis and content workflow extension — 2026-10-27

- Added a conditional 7-day demand signal, low-sample warnings, and a hold on replenishment when recent sales are zero. Exported observed demand, assumed stock/cost, and recommendation reasoning as CSV.
- Added editable and persistent short-form text drafts behind an independent module router and table. No video generation or publishing is present.
- Added a descriptive pre/post action view requiring seven daily rows on each side of the completion date, including explicit zero-sale rows. Missing data blocks the comparison; current stock is labelled separately.
- Backend tests cover demand surge, sparse/absent demand, short-form persistence, and complete/incomplete action windows. Python tests and TypeScript typecheck pass. Vite bundling is still blocked in this Codex shell by esbuild `spawn EPERM`, so browser visual QA remains to be done in Antigravity.

## Editorial UI redesign — 2026-10-27

- Used the Superpowers brainstorming, planning, inline implementation, and verification guidance with an owner-provided wellness UI image as a visual reference. The image was copied to `docs/references/` and the design decision is recorded in `docs/superpowers/`.
- Added a warm cream/pastel visual system with larger type, visible focus, priority cards, and plain-language next actions. The Olist screen now introduces actual sales versus assumed inventory before detailed numbers. Mobile navigation now opens from the menu button.
- React TypeScript check, CSS parsing, and the eight backend tests pass. The local Vite start still fails with esbuild `spawn EPERM` in this Codex shell, so a visual check in Antigravity is required before claiming the final layout is finished.
- Browser review on 2026-10-27 used a temporary static bundle produced by the esbuild CLI, served locally at `127.0.0.1:5173` against the running FastAPI backend. The overview, Olist action cards, and the action-card link to numeric evidence rendered and responded. This is not a Vite hot-reload server.
- Review fixes: kept sidebar labels on one line; translated Olist category names in the evidence, top-sellers, and scenario comparison tables; and explained that a product with 30-day sales but zero sales in the last seven days needs demand review before replenishment.
- Narrow-screen browser review used an approximately 355px viewport. The priority cards and Olist cards stacked, the menu opened and navigated, and the evidence table stayed inside its own horizontal scroll region. Fixed the mobile header wrapping and the page-level overflow.
- Downloaded the Olist inventory template through the browser and inspected its CSV header and example rows. The analysis CSV endpoint returned HTTP 200 with `text/csv` for a saved five-product scenario. CSV upload was not repeated during this UI pass because existing scenario imports were already verified.
