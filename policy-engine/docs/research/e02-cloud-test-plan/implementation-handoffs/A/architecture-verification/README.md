# Architecture verification handoff evidence

This package records the architecture-gate failure at pre-slice checkpoint `905820ceac5860c7d1c4ebcbdde7b1265afb0b15`, public-surface regeneration, and trust-posture generator/semantic review. It does not claim an overall architecture pass. The public-surface render was generated at the base and both output byte streams were read back from candidate commit `65ea9072e4877e2198f1ba96b72d2892b2f3fbbb`; the trust posture candidate remains in ignored scratch and is held for technical and semantic review.

## Deciding results

- The full guardrails run at pre-slice checkpoint `905820ceac5860c7d1c4ebcbdde7b1265afb0b15` failed with exit 1 after 197.654 seconds. The actual public-surface slice base is `9794b716a74aee98545449ac97dc98825d2471de`, the parent of candidate `65ea9072e4877e2198f1ba96b72d2892b2f3fbbb`. Its full stdout/stderr and environment/input receipt are copied byte-for-byte here. It reported stale public-surface JSON and Markdown, deep-import creep, and trust-posture output mismatch. The deep-import baseline was not changed. There is no full guardrails replay at the actual slice base or candidate; the older red is not attributed under P41.
- The canonical AST public-surface renderer passed for its two-output scope. The generated inventory and Markdown hashes match the corresponding files read back from `65ea9072e4877e2198f1ba96b72d2892b2f3fbbb`. The renderer manifest predates the trust generator run and is named to preserve that chronology.
- The trust-posture owner generator completed with exit 0 and `verdict=PASS` on `9794b716a74aee98545449ac97dc98825d2471de`. This proves generation/check execution only. The 2,557,025-byte owner stdout, 2,376,651-byte generated candidate, and 472,669-byte full structural diff remain in ignored scratch; their exact paths and SHA-256 digests are in `architecture-verification.json` and in the copied trust semantic review. They are intentionally not duplicated into this repository.
- The semantic review fails publication acceptance: 44 status-sensitive changes include loss of 13 deny-use values on each of three scope-specific claims as the conditional S10 source becomes `runtime_bound`. The restrictions remain present in a separate runtime-bound record, and all three claims remain blocked; no status/closure promotion is claimed. A source-to-scope association repair and appointed owner decision are outstanding.

## Evidence files

Each copied output is byte-identical to its ignored source. SHA-256 and byte counts are bound in `architecture-verification.json`. `trust-semantic-review.json` contains the all-19-root-key comparison summary, all three affected claim records, the 44 status-sensitive row review, and old/current source blob attribution. The full 896-row structural diff is cited by its ignored path and hash, not copied here.


The candidate receipt is pinned to the exact two-path commit `65ea9072e4877e2198f1ba96b72d2892b2f3fbbb` (`9794b716a74aee98545449ac97dc98825d2471de` parent). The branch later advanced to `00fa6d83ee3c04973b95b0cf7b924fd617ef8071`; those descendant changes are outside this handoff footprint.
