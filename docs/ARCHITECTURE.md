# Architecture and module boundaries

## Application layers

- **React UI:** dashboard, product detail, import flow, and action log.
- **FastAPI API:** validates requests and exposes product, analysis, import, and action endpoints.
- **Domain services:** calculate metrics and recommendation rules independently of HTTP and presentation.
- **SQLite database:** persists products, dated sales rows, and action history for the local MVP.

## Data flow

`CSV / seeded sample -> API validation -> database -> analysis service -> recommendation response -> human action log`

`completed action + complete daily sales for 7 days before and after -> descriptive comparison (no causal attribution)`
