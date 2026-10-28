# Olist demand + scenario contract

## Source and transformation

Source: `jeongminimi/Olist-E-Commerce-Data-Analysis`, forked from `dino-21/Olist-E-Commerce-Data-Analysis`, with the Kaggle Olist public dataset. The importer reads the original compressed orders, order items, products, and category translation files. It requires `order_status=delivered` and purchase date from 2017-01-01 through 2018-08-31. It joins `order_items.order_id` to `orders.order_id`, groups by `product_id` and purchase date, counts one order-item row as one sold unit, and sums `order_items.price` as item revenue in BRL. Freight and `payment_value` are excluded. Every imported SKU is `OLIST-` followed by the 32-character product ID.

The importer is idempotent: an existing import record returns its metadata without inserting rows again. It saves a checksum of the four compressed source files, date range, order count, item count, and product count. Imported Olist products are excluded from the original demo workspace and appear only in the Olist workspace.

## Simulation CSV

Download the latest top-20 template in the Olist workspace. All rows in one file have the same `scenario_name` and `as_of_date`. Each SKU appears once. Fill every blank field before upload.

| Field | Meaning | Provenance |
|---|---|---|
| `scenario_name` | User's scenario label | User input |
| `as_of_date` | Historical Olist date with a full 30-day lookback | User input |
| `sku` | Imported Olist product ID with `OLIST-` prefix | Olist |
| `stock_on_hand` | Assumed saleable stock | Simulation |
| `inbound_units` | Assumed incoming stock | Simulation |
| `lead_time_days` | Assumed replenishment lead time | Simulation |
| `target_cover_days` | Assumed target days of cover | Simulation |
| `unit_cost` | Assumed per-unit cost in BRL | Simulation |

Upload creates a new scenario without changing Olist demand or another scenario. Empty or invalid fields reject the entire file, rather than silently importing partial results. The app evaluates sales from `as_of_date - 29 days` through `as_of_date`. A scenario can use an earlier date within the imported range if it still has a complete 30-day lookback.

Two scenarios can be compared only when they contain the same products and use the same historical date. The comparison keeps observed 30-day sales fixed and shows how the assumed inventory changes stock cover, rule-based risk, estimated inventory value, and suggested replenishment. It is a sensitivity comparison, not an observed sales improvement or a causal experiment.

## What results mean

- Sold units and revenue are observed historical Olist figures for the chosen window.
- Stock cover, stockout risk, replenishment quantity, and estimated gross margin combine observed sales velocity with simulated values.
- A recommendation is a rule result for a hypothetical inventory state. It is not proof that an action changed actual sales, margin, or retention.
- The Olist dataset has no original inventory snapshots, replenishment lead times, unit costs, campaign exposure, or randomized A/B assignment. Those cannot be recovered from order history alone.
- Olist source data in the referenced repository is labelled `CC BY-NC-SA 4.0`. Confirm the source license before any commercial reuse.
