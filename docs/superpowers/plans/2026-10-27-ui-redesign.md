# MD Decision Lab UI Redesign Implementation Plan

> **For agentic workers:** Apply Superpowers' design, small-task implementation, review, and verification workflow. Work inline in the existing folder because this local project is not yet a Git repository.

**Goal:** Make the MD Decision Lab understandable at a glance to a first-time, nontechnical MD while adapting the owner's pastel editorial visual reference.

**Architecture:** Keep all backend contracts. Add a scoped visual layer and presentation components to the existing React screens. Preserve the existing tables as expandable evidence.

**Tech Stack:** React 18, TypeScript, Vite, CSS.
**Spec:** `docs/superpowers/2026-10-27-ui-redesign.md`

## Global constraints

- Historical sales, simulated inventory, and estimated margin remain explicitly labelled.
- The reference image is a mood reference, not a production asset.
- Maintain readable contrast and minimum 14px supporting/table text.

## Review focus

- No scenario selected: show a clear next step without an empty analysis card.
- Scenario with no urgent products: say there are no urgent alerts and still show reviewable products.
- Long product labels and narrow screens: wrap without clipping actions.
- Interactions: all existing CSV upload, download, comparison, and detail buttons remain reachable.

### Task 1: Visual system

**Files:** Create `frontend/src/editorial.css`; modify `frontend/src/main.tsx` to import it after the existing styles.

- [x] Add typography, spacing, surface, focus, and responsive tokens inspired by the reference.
- [x] Verify TypeScript and parse all CSS files; inspect the desktop layout in a temporary static browser preview because Vite cannot start in this shell (`spawn EPERM`).

### Task 2: Action-first overview

**Files:** Modify `frontend/src/App.tsx`, `frontend/src/editorial.css`.

- [x] Place a prominent “today's priorities” section before metric totals.
- [x] Show product, reason, and one next action in readable cards using existing ProductAnalysis values.
- [x] Keep the existing data table for detailed review.

### Task 4: Verification and review

**Files:** Update `docs/BUILD_LOG.md` and the plan checkboxes.

- [x] Run frontend TypeScript check, CSS parsing, and backend tests. Vite launch attempted and failed with esbuild `spawn EPERM` in this shell.
- [x] Review code against the acceptance checks, including a narrow-screen browser check. Vite hot-reload remains unverified because this shell blocks esbuild child-process spawning.
