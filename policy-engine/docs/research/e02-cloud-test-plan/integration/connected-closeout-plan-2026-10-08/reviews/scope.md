# Final delta review: scope fixes

Delta-only read of the requested B11/B156 edits; no new whole-unit review and no runtime checks.

**B11 blocker resolved at planning level.** `05-verification-and-release.md` now states the full surface condition: label proxy/inspection value as heuristic, retain picked/deferred reason, and do not assign publishability. It explicitly says controller-positive and exhausted-budget evidence alone are insufficient, and routes this projection check to Q2. `findings.json` routes B11 through Q0 + Q2 while retaining `author_proposal: limited` and `G_closure: not_adjudicated`, so the edit does not pre-adjudicate closure. It also keeps provider/invoice truth out of B11. The previous omission is resolved; Q2 must carry the stated surface discriminator in its eventual receipt.

**D B156 blocker resolved.** `06-inputs-and-deferrals.md` now enumerates all four original predicates: same effective request reuses; changed input version re-executes without stale score; the new control actually invokes its callback; ordinary-attempt history/state remains unchanged. It expressly allows a mocked callback when the real orchestrator/cache path is exercised, and excludes universal product evaluator/default/production-history requirements. This matches the bounded original criterion without statistical-independence proof or persisted production history.

No further scope blocker found in this requested delta. D B109/B117 and F LA-035 remain as assessed in the prior review; no changes to those conclusions.
