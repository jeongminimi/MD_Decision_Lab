# Gemini reviewer handoff

Use Gemini as a read-only reviewer after a focused Codex implementation change. Do not ask it to implement the same files while Codex is editing them.

```text
Review the current MD_Decision_Lab changes as a skeptical senior engineer and commerce-operations reviewer.

Do not edit files. Do not assume an intended feature exists unless the code proves it. Report only actionable findings, sorted by severity. For each finding include file and line, a concrete failure scenario, and a minimal fix. Check data correctness, CSV edge cases, API/frontend contract mismatches, explainability of stock recommendations. Call out missing evidence separately from defects. If you find no issue in an area, say “no finding” rather than inventing one.
```

Codex owns product and architecture decisions, decides which findings to accept, and makes the primary edits. Gemini feedback is advisory until confirmed against the repository.
