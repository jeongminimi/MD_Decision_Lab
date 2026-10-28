# MD Decision Lab — working rules

## Product objective
Help a small commerce MD turn product-level sales and stock data into traceable replenishment, promotion, and live-exposure decisions. The first version is a portfolio demonstrator and must not claim proven revenue gains.

## Roles
- Codex owns product decisions, architecture, domain logic, and primary implementation.
- Gemini is a reviewer and secondary helper. Ask it to inspect changes, identify edge cases, and suggest focused fixes. Do not let two agents edit the same files at the same time.

## Domain rules
- Show the numbers and rule behind every stock-risk label and recommendation.
- Clearly distinguish measured input data from estimates and suggested actions.
- Do not describe a recommendation as an observed business result.
- Keep the short-form content workflow behind its own input/output boundary. It may consume an explicit product brief, but must not import or mutate inventory-analysis internals. This boundary should allow extraction into a standalone service later.
- Do not add automatic publishing, real customer data, or external AI API calls in the MVP.

## Implementation
- Frontend: React + TypeScript + Vite.
- Backend: FastAPI + SQLAlchemy + SQLite for the local demonstrator.
- Keep calculations in backend services, not in React components.
- Use synthetic demonstration data and label it as such.
- Prefer small, reviewable changes. Preserve existing user data and never overwrite an existing database on startup.

## Portfolio honesty
Describe the project owner's role as problem framing, workflow and rule definition, AI-assisted implementation direction, and output review unless they personally performed additional coding. Never attribute AI-generated code to the owner as unaided coding work.
