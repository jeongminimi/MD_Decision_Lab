# MD portfolio direction implementation plan

Follow Superpowers' design → small tasks → red/green tests → verification approach inline in this existing folder. The project is not a Git repository, so do not create a worktree.

1. Add failing backend tests for two-option gross-profit arithmetic, inventory feasibility, and non-reorderable products.
2. Add a calculation service and a fashion comparison API. Keep observed historical data and user assumptions separate in the response.
3. Add a guided comparison panel to the apparel product detail view and plain-language labels for assumptions and limitations.
5. Run backend tests, TypeScript, production bundle, and local HTTP checks. Check that the UI bundle and API both expose the new flow.

Review focus: zero sales, no stock, discount below cost, reordering disabled, and dates/provenance shown consistently.
