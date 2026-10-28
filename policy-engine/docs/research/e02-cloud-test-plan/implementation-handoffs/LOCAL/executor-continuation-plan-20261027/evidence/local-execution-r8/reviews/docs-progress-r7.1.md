# Independent review — E02 documentation progress r7 + r7.1

## Scope and verdict

Reviewed the r7 and r7.1 manifests, all declared postimages, the complete execution-ledger and state postimages, and the specifically cited C07/C45 review artifacts. This was a documentation/evidence review only: no tests, product imports, canonical writes, index/refs changes, or runtime operations. **Accept the sparse composition after a small append-only current-view delta** for later independent review results, while preserving the source-time observations and explicit limits below.

## Integrity and overlay binding

- r7 manifest `LOCAL/raw/e02-execution-20261027/docs-progress-r7/manifest.json`, SHA-256 `6570e685e0c23de8471c0187bf810e7fe47569d707052dbb858b53c797937fa0`: 50 rows / 531,049 postimage bytes.
- r7.1 manifest `LOCAL/raw/e02-execution-20261027/docs-progress-r7.1/manifest.json`, SHA-256 `5d60aa0183a7e0bb3089e4934f51a7f628c020952a483c62f80146c757f854ed`: 15 rows / 376,079 postimage bytes.
- Verified every postimage size and SHA-256. For every declared raw binding, verified exact raw hash/size and lossless gzip decompression. No missing payloads, hash/size mismatches, raw-byte mismatches, or duplicate targets.
- r7 replaces exactly the two current-view documents from r6.1; both prior hashes match. r7.1 likewise replaces exactly those two r7 documents; both prior hashes match. No unbound overlay collision found. The chain is explicitly `r6 -> r6.1 -> r7 -> r7.1`.
- Source cut `67beb3461ab96c4cb64b92226228da39b30bcb06` resolves to tree `306e3c150f6a1368f23c8ebece35aeec3feb180b` in the author Git object database. The proposal treats this as an observed case cut, not a future HEAD promise.

## Substantive claims

The ledger appropriately separates old-source and later-source outcomes. C45's old-source timeout/progress bytes are ERROR/unqualified; the separate finite-source failures and earlier C37/Core failures stay bound to their own commits. The later C45 310-PASS result is a selected consumer cohort at `67beb`, with its own 1,817-path finite readset qualification; it does not imply removals, callback-thread B69, universal currentness, acceptance, or closure. The available `C45-independent-review.md` is a prompt review only (GO for standalone launch), not an independent actual-result review. Thus “actual independent result review pending” remains correct.

C07's 14-PASS 67beb selection and its synthetic predecessor-CAS pilot are distinct evidence. The selection has its finite 77-path qualification; the pilot has separate inputs and the actual reviewer reconciled source/profile/artifacts. Neither is the original HTE rerun or a product/S1/G pass. R3's 14 FAIL remains distinct from C05. C43 stays bounded numerical GO with strict cached BLAS-byte identity unestablished. C64/C65 remain reconstructed candidate diffs with bounded source reviews and explicit consumer/removal gaps, not composed capabilities. The 26/127/282/291/319 criterion denominator, B198, and no-G-closure boundary are preserved.

The evidence package follows the A-D distinction: deciding outputs and review bytes are included; Git/input-recipe evidence is cited rather than copied; ignored locators are not presented as transferred bytes; the mismatched historical root-live bytes are not reconstructed. Finite imported-path readsets are bounded observations, not a repo-wide census.

## Required append-only current-view delta

1. **C50 stale sentence.** Both r7 and r7.1 retain the earlier paragraph saying the actual C50 triplet “awaits independent result review” (paragraph 125), while their later r7 update says the subsequent actual review gives bounded GO (paragraph 135) and state records `c50_actual_review.status = bounded_GO`. This is an internal contradiction, even though the newer status is otherwise correctly represented. In a subsequent delta, mark the paragraph-125 statement as a historical r6.1 snapshot superseded by the r7 review, or rewrite the current view while retaining historical fact. Preserve the bounded Python/Pydantic witness boundary and do not broaden to BLAS, issuer/source provenance, production calibration, G, or closure.
2. **C07 pilot review arrived later.** r7.1 correctly says the synthetic pilot's independent actual review was pending at its observation. A later independent review is now available: `LOCAL/raw/e02-execution-20261027/reviews/C07-cas-owner-query-pilot-r3-actual.md`, SHA-256 `175825f666ed8469c3866e55724a498b00b4f77c2ca07d6cd48151fde26a6ac8`; machine readback `.../C07-cas-owner-query-pilot-r3-independent-readback.json`, SHA-256 `82013de2ca0b82113029e729b0a18046595b42e7dbe58fbdb5f35eb5516dc6ba`. It gives bounded actual GO for one synthetic predecessor-CAS write at the frozen source/profile, reconciling source, output profile and local artifacts. It explicitly says the original HTE failure was not replayed and the unit cohort, removal control, broader readiness and external authority remain separate. Add those review bytes and update only that pilot's current review state; retain r7/r7.1's pending state as an as-of observation.

## Boundary

The r7/r7.1 outputs are sparse proposal postimages awaiting coordinator composition; verifying these local bytes is not itself delivery to the canonical evidence tree. No G acceptance or formal finding closure is assigned. The source cut and each runtime cohort remain precisely bound to their own source, selected test scope, backend/profile and readset.
