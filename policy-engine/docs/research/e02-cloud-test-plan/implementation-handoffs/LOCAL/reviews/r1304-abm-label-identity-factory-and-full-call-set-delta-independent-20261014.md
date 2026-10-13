# R1304 — ABM label-identity factory and full call-set delta review

**Disposition: GO-LIMITED for root composition.** The R1301 successor resolves the R1299 fixture-import blocker with one generic label-to-SHA-shaped-ID factory across the complete `_ref` call set. I found no remaining `g` rejection path or intended negative-control displacement in the proposed postimage. This is static review only: no tests, imports, runtime checks, source edits, or Git writes were performed.

## Bound input and postimage checks

- OWN branch `codex/e02-unified-local-20261009`, HEAD `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d`, tree `1355896e91789026d21396d2b087c63827ab251b`.
- Source frame `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1267-20261014.json` @ `a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803` (590 physical source paths).
- R1301 patch `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1301-abm-fixture-identity-factory-and-whole-ref-call-set-successor-20261014/proposal.patch` @ `beb9fd0b7c6b44a2afa72bbded3003a4797260bf7f88c7df95f95dfd8b3a62e2`; manifest `manifest.json` @ `8ad2938ea25bfa6ced3ad0a32d00d731b6915253b6cd2be838fc207e346e5ece`; decision `decision.md` @ `2d43d699aa470c2c1c8c8cd35c93e30b609bcf803031c316301ee2e73bdd3d75`.
- Both candidate preimages match current files. I reconstructed both unified-diff postimages in memory; their SHA-256 values match the manifest (`test_abm_receipt_strangle.py` → `e1e44e5f349d1248c95ca3140ee9d621f8265d9113716f1072c9f5a2ad23a472`; `test_source_bound_risk_candidate.py` → `8c7365117a9ceeec67c8a7bcaf84f2177895e46cb9100fcb1da29dfbbb78e19f`). Both generated Python files parse with stdlib AST. No product source paths are in the patch.

## Complete reference-factory quantity and negative controls

A stdlib AST walk over the complete `policy-engine/tests/unit/foundry/methods/catalog/simulation/test_abm_receipt_strangle.py` file (one `.py` file) finds 26 `_ref` call sites. Their full label histogram is `0`–`9` once each, `a` three times, `b`/`c`/`d`/`f` once each, `e` three times, and `g` six times. Every call passes a string literal; no dynamic or direct helper bypass was found in this set.

The R1301 helper hashes each fixture label with SHA-256 and prefixes the lowercase digest with `sha256:`. Consequently all six former `g` calls now have valid digest *shape*, including the intentionally wrong-kind and wrong-media parametrized controls. Those cases preserve their wrong `kind` or `media_type` field, so the type discriminator is no longer masked by an invalid digest. The explicit raw `not-a-content-address` case remains unchanged and bypasses `_ref`, preserving a separate malformed-digest negative. Label hashing only creates structural test identifiers; it does not claim matching artifact bytes, producer provenance, or source custody.

This closes the R1299 finding across the whole helper call set rather than replacing only the two late-found calls. The remaining R1276 cases still test malformed status/schema and the valid positive payload; no test expectation is narrowed or rewritten by this successor.

## Producer bridge and reference coordinates

The R1301 patch keeps the R1282r2 producer bridge test postimage byte-for-byte unchanged. It is the same candidate already reviewed in R1299: the `foundry_source` fixture calls the existing `_build_foundry_source`, which compiles with `compile_foundry`, executes via `execute_foundry`, obtains selected-profile Core CAS outputs, reads the `SimulationResult` and `FoundryExecutionInputBasis`, converts with `build_abm_result_from_simulation`, writes through `persist_abm_result`, and calls `load_abm_result` by the emitted ref.

The test compares the complete selected ref tuple (`artifact_id`, `kind`, `media_type`, `manifest_profile_sha256`) across the produced basis ref, serialized Core result, ABM conversion, and fresh IR load. The persisted `InputRef` schema carries the basis artifact ID and selected manifest profile; the test checks both on the actual ABM manifest edge. This is a controlled synthetic Foundry producer/CAS bridge and is still **UNRUN**. It is not live production evidence or external authority.

## Boundary and disposition

R1237 remains an unresolved author proposal on the ABM3 version namespace, publication, and migration choice; R1301 does not settle it. The R1237 decision is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/r1237-abm-version-namespace-and-reader-migration-proposal-20261013.md` @ `f7be74a4941f82dfbfb0e8115c2d62014b07c2ee482c211a56bcd2c0b3c85e70`.

P40 classification: **same fixture-reference validity class, second finding; the generic identity factory now covers all 26 call sites.** Candidate is suitable for root composition/application review, not test acceptance or G/publication acceptance. Pytest, product imports, and the producer bridge remain unrun; `closure_ids=[]`.
