# MD Decision Lab UI redesign

## Reference and goal

Visual reference: `docs/references/wellness-ui-reference.jfif` (provided by the project owner). Use its generous cream space, editorial headings, soft lilac/peach/sky lighting, rounded cards, and calm pacing. Do not reproduce the wellness imagery or use the reference screenshot as an app background.

The first-time user is an MD without development knowledge. Within five seconds they should understand which product needs attention, why, and what they can do next. Keep observed sales, assumed inventory, and estimated margin visibly distinct.

## Decisions

- Preserve the existing React, FastAPI, database, calculations, and routes. This is a presentation and interaction upgrade.
- Lead the overview with a plain-language action hero and a short priority list. Put revenue totals after the urgent question.
- On the Olist screen, explain the source in one sentence, show the next step, then show action cards before the dense data table. Keep the table available for audit.
- Use warm paper, dark ink, controlled pastel surfaces, editorial serif headings, and clear sans-serif body copy. Gradients decorate summaries only; risk labels and data stay on solid high-contrast surfaces.
- Minimum typography: 16px body, 14px supporting and table copy, 12px small labels. Buttons are at least 14px. Do not use color alone to explain a state.
- On narrow screens, stack cards and keep every primary action reachable without horizontal scrolling. The detailed table may scroll horizontally.

## Acceptance checks

1. Overview answers: “What needs my attention today?” and provides a visible next action.
2. Olist explains real historical sales versus hypothetical inventory without requiring the user to open a tooltip.
3. At least one recommendation is understandable before opening numeric details; detailed evidence remains accessible.
4. No data or analysis rule changes; both demo and Olist data still load.
5. Desktop and narrow-screen layouts remain usable; keyboard focus is visible.
