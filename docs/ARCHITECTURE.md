# Architecture and module boundaries

## Application layers

- **React UI:** dashboard, product detail, import flow, and action log.
- **FastAPI API:** validates requests and exposes product, analysis, import, and action endpoints.
- **Domain services:** calculate metrics and recommendation rules independently of HTTP and presentation.
- **SQLite database:** persists products, dated sales rows, and action history for the local MVP.

## Short-form module boundary

The content workflow is a separate module with a versioned contract:

`POST /api/shortform/v1/draft: ProductContentBrief -> ContentDraft`

The brief contains only approved product facts, campaign/action context, audience, offer, and tone. The short-form module returns editable hook, script beats, caption, and CTA. Its own `/drafts` endpoints save and reload approved briefs and edited drafts in a separate SQLite table, without a foreign key to inventory. It must not query inventory tables directly or write back into inventory. A future standalone service can implement the same versioned contract and receive the brief over HTTP or a queue; the commerce app would then call the service through an adapter. Keep service configuration and provider credentials outside the shared contract.

For MVP, the content draft generator uses a local deterministic template. A model adapter can be added later without coupling inventory logic to a model vendor. It does not render video or post to social networks.

## Data flow

`CSV / seeded sample -> API validation -> database -> analysis service -> recommendation response -> human action log`

`completed action + complete daily sales for 7 days before and after -> descriptive comparison (no causal attribution)`

`approved product/action brief -> short-form module -> editable content draft`
