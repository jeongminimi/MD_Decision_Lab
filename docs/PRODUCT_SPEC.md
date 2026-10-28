# Product specification

## Problem

Small commerce teams often move product, sales, and inventory data between spreadsheets. It is difficult to notice a likely stockout early, identify inventory that needs a sell-through action, and remember whether a chosen action changed the outcome.

## Target user

An apparel or small-brand MD who manages product availability, replenishment, promotion, and live-commerce exposure using sales and inventory exports.

## Core workflow

1. Import or review product and daily-sales records.
2. Inspect sales velocity, days of cover, inbound quantity, and lead time.
3. Review a transparent risk label and recommended next action.
4. Record the MD's selected action and rationale.
5. Compare the product's later sales, margin, and stock with its pre-action state.

## MVP scope

- A relational database for products, daily sales, and action history.
- Seeded synthetic apparel data with an explicit demo-data label.
- Dashboard summary and searchable/filterable product table.
- CSV import for daily sales.
- Rule-based stock risk and action recommendations.
- Action logging and before/after comparison foundations.
- Responsive desktop-first UI suitable for a portfolio walkthrough.

## Out of scope for this two-day MVP

- Direct integrations with live POS, ERP, marketplaces, or warehouses.
- Automatic purchase orders, discount changes, or public social publishing.
- Predictive machine learning presented as validated forecasting.
- Real customer information or actual company data.
- External GPT/Gemini API calls from the product. GPT and Gemini are development agents in this workflow, not runtime dependencies.
- Claiming a measured increase in conversion, revenue, or margin.

## Product success criteria

- A reviewer can import a sales CSV and see the product metrics change.
- Every risk label can be explained from visible inputs and documented thresholds.
- A user can record an action against a product and see it in the history.
- The owner can explain the domain problem, rules, data model, limits, and their own role honestly.
