# Independent R1/R2 review

Review target: `672f5514e2733a782b49a56425b67294928de78a` (tree `8b41d7c743853588228381d4a9fc1f9c76046763`, parent `8e69d23ee61a640621a487243a59107f0d1f232f`). I did not switch HEAD or edit product, test, configuration, or release files. I read target source with `git show`; the selected producer, state-branching, pool/stream, and cleanup-oracle paths checked for local diffs were unchanged. Other source statements below cite the pinned target. The repository worktree contains unrelated active edits.

## Decision

The R2 physical-cleanup path is well supported by a real connector/CAS consumer test and the pool admission tests. The source looks coherent within the documented finite JSON/Pydantic model profile. The candidate is not ready for R1 closure: one newly committed validation-graph test does not collect, its release evidence names another absent test, and the recorded R1 aggregate log has no pytest summary or exit status. B61 and B148 remain criterion-specific `verification_missing` based on their own receipts; do not promote their partial checks to closure.

## Findings

### R1: the new validation-graph oracle cannot collect

`tests/unit/scientist/orchestration/engine/test_producer_validation_graph_oracle.py:38` imports `.test_producer_model_scope_oracle`, which is absent from the complete pinned tree. `git ls-tree -r` also confirms it is absent from the current worktree. Running the file produced `ModuleNotFoundError` during collection; no test body ran. The captured output is in [producer-validation-collection.txt](r1-r2-review/producer-validation-collection.txt).

This is a **NEW test-companion/collection class**, not another runtime ladder repair. The same missing path appears as evidence in `release-fragments/unreleased/2026-10-07-e02-b53-producer-publication-reconciliation.toml:7`. Add the minimal current helper or make the oracle self-contained, then run this file. Do not claim the producer validation-graph semantic test has passed before that run.

The release fragment also says runtime/style/typing/matched-removal checks are `UNRUN` at line 13, while the local receipts report later focused checks; its `public_surface_inventory_reviewed = false` at line 15 should be reconciled with the additive `PreparedSKGRead`/`PreparedSKGReadReceipt` facade exports. The source diff to `read_api/academic.py` is additive and retains all prior entries, but the release companion currently does not accurately express the candidate evidence state.

### R1: the aggregate pass is reported but its deciding output is incomplete

`LOCAL/r1-prepared-b/r1-13-contours-collect.log` records the 13 affected consumer files plus the separate `test_producer_scope_reconciliation.py`, with collection counts summing to 267. The receipt reports 267 passed. However, `r1-13-contours-after-valid-ref-fixture.log` has 151 lines and ends at pytest's warning-docs footer: it contains no final `267 passed` summary, command, or exit status. The progress output reaches 100%, which is not a deciding pass receipt. Hashes for both local files are recorded in the report's source evidence below. Per HANDOFF and P29, retain a complete command/output/exit record on the frozen source before presenting the aggregate as independently verified.

The 13 affected consumer test paths named in the receipt are:

1. `test_state_branching.py`
2. `test_state_merge.py`
3. `test_native_state_cache_semantics.py`
4. `test_idempotency.py`
5. `test_engine_executor_idempotency.py`
6. `test_async_cache_recovery.py`
7. `test_cache_reference_custody.py`
8. `test_async_executor.py`
9. `test_async_executor_hardening.py`
10. `runner/test_activity_worker.py`
11. `runner/test_serialization.py`
12. `runner/test_serialization_e02.py`
13. `runner/test_state_merge.py`

The separate defining consumer is `test_producer_scope_reconciliation.py`. The run does not include `test_producer_validation_graph_oracle.py`; this is confirmed by the collection list and its independent collection error above.

### B61: retained-source closure remains open

The whole `test_skg_snapshot_replay.py` run collected 22 cases and reported 20 passed, with the timed and async real-workflow cases failing at the original 30-second budgets. Both routes passed in separate real-workflow runs under 90-second test/workflow budgets (5.80 s and 5.71 s). This suggests the whole-file failures are load-related, but the cause is `not_established`; the 30-second whole-file replay has not been repeated after freeze. Keep B61 at `verification_missing` until the exact original whole-file command passes or a bounded supported reason is established.

The retained-byte discriminator and property-removal receipts are useful: the direct witnesses plus a real sync workflow consumer fail under the locator-only removal, and the source bytes were restored with matching pre/post SHA-256. They establish that narrower property, not all B61 criteria.

### B148: foreign-owner controls pass, full admission criterion remains open

`test_bound_import_preservation.py` passed 12/12; its matched admission removal caused the six foreign-owner directory/archive/exact-view cases to fail as expected. The exact target contains `test_transfer_import_fresh_process.py`, but the receipt says it has not run. The target does not contain `test_import_admission_noop.py` (the full-tree exact lookup is in `source-census.txt`). Therefore the current evidence does not cover the unbound claimed/unclaimed and conflicting-view controls, and does not finish B148. Keep `verification_missing` pending the fresh-process positive and complete exact-candidate import controls. Do not turn the foreign-owner removal into a claim of whole B148 closure.

### Producer callback admission: documented bounded residual; P40 same class one level deeper

The gate's supported property is narrow live-path mutation accounting over finite ordinary model/container graphs. `_ordinary_model_type` and the assignment path reject custom Pydantic hooks and detached validator sibling mutations; the engine README explicitly says arbitrary custom runtime objects, validator-closure effects, reflection, and explicit base-class mutators are outside this guarantee.

There is a concrete boundary case one level below that model-hook screen: after normal state construction, assign a custom object to `state.params['probe']` (the nested value is not revalidated by Pydantic). `_validate_producer_state` accepts it because `_validate_mutation_attachment` walks dict/list/tuple/BaseModel but returns on unknown leaves (`state_branching.py:1325-1351`). The following `snapshot_state` recursively deep-copies the top-level mappings (`:276-286`), invoking that object's `__deepcopy__`. The local falsifier output is in [custom-object-admission-probe.txt](r1-r2-review/custom-object-admission-probe.txt).

P40 classification: **same callback/admission class, one level below BaseModel hooks**. This is the second-level escape; do not patch one extra object type. The current README already bounds arbitrary custom runtime objects out of scope, so preserve that limitation unless the owner intentionally widens the runtime invariant. Smallest missing capability for widening is a recursive, fail-closed canonical JSON leaf admission check before any snapshot/copy. The falsifier is exact: hold the nested object in state, keep its declaration/state shape intact, and observe admission green followed by `__deepcopy__` side effect. The engine does not currently have that generic leaf validator. This is a bounded residual, not evidence that supported ordinary JSON/model graphs are broken.

### R2: meaningful physical and fresh-CAS consumer evidence

`test_stream_cleanup_recovery.py` exercises the real `EventStreamConnector`, `ConnectionPool`, `process_stream_dataset`, and `CursorStore`/`FileSystemCAS`. Its full-file output reports 6 passed. The tests keep a failed physical handle reachable through cleanup retry, assert the same handle is disconnected again, verify the permit remains owned until cleanup succeeds, and exercise actual task cancellation after source yield. The frontier crash/reopen case reopens fresh CAS/cursor readers and checks exact raw-row replay, ordered windows, contributor refs, and committed frontier state.

`test_pool_e02.py` has 16 collected cases; the receipt reports 16 passed, but its retained `pool-focused-after-source.log` contains only progress dots, no terminal summary/exit. The R2 cleanup file does have a complete deciding summary. The streaming collection receipt lists 70 cases in `test_e02_c_streaming_oracle.py`, 50 in `test_streaming_runtime.py`, 6 processing-guarantee tests, and the targeted cleanup/budget oracles; the short `stream-*focused` logs are focused three-case outputs, not a whole-file run. No claim is made that all 135 collected stream tests passed.

The physical property is measured rather than a marker: same-handle cleanup retries and permit state are asserted after actual connector disconnect failure, and the new CAS reader checks the committed artifacts after a simulated crash boundary. The tests do not claim a deployed supplier's external event/version authority; the Data Plane README and release note leave that explicitly separate.

## API / public surface

At the exact target, `data_forge/read_api/academic.py` only adds lazy exports for the existing `PreparedSKGRead` and `PreparedSKGReadReceipt`; all prior map entries remain. The engine uses the canonical producer through that facade and documents the retained descriptor as operational source custody, not source authenticity or scientific evidence. This preserves the G facade surface and avoids treating the new `skg_snapshot.py` as an issuer. The release fragment needs its inventory/status fields reconciled, as above.

## P40, P37/P38, and status buckets

- Missing oracle companion: **NEW class** (test collection/evidence wiring); repair the companion once and rerun the oracle.
- Arbitrary custom leaf callback: **same producer-state callback class, one level deeper**; second-level finding. Widen once to recursive canonical-value admission or retain the declared bounded residual and its falsifier. No local ladder patch.
- Checkpoint adapter keyword gaps described in the existing receipt were fixed at the shared supplier seam; the first checkpoint discriminator passes. This review found no new same-class deadline escape in the inspected paths. The separate original checkpoint bundle remains outside this scoped no-heavy review.
- P37/P38: the supported gate recomputes actual mutation operations/paths against declared `state_writes`; the permission basis itself remains the producer/registry's declared contract and is not evidence of a minimal grant. Within that contract, the property is the live mutation path, not a marker or `state_writes` string. The named divergence is the unsupported custom leaf above: the declared JSON-shaped state is trusted at nested `Any`, while `deepcopy` executes its callback.
- Formal status remains with G. This report does not close findings or certify a whole-package replay.

## Deciding outputs and source identities

Full moderate R1/R2 test outputs remain in `LOCAL/r1-prepared-b/`; avoid copying them. Their hashes are:

- `r1-13-contours-after-valid-ref-fixture.log` — `613ec3672852a1d14803a6bdaa6d69c6f1f076edc8956b4a88202a816a6eb7be` (incomplete footer; no pytest summary/exit).
- `r1-13-contours-collect.log` — `e69cfe8178c4c6d9808a94093db4e877c817c05bb895b56400cbc7534fe0eadb` (collection counts only).
- `r2-stream-cleanup-wholefile.log` — `f23834603394af90dc78b3fe6cff327e4577526eaa1d24f92909fc50fa6c4d39` (6 passed, 1.01 s).
- `pool-focused-after-source.log` — `ecf57d762b443151696ef4727347520d0d5715719bac1e0cd93caddf627ffa61` (progress only; no terminal summary).
- `b61-skg-snapshot-wholefile.log` — `5c529f3a9845af493e61d5df50cbd99b5247e1d2f67b42419739c69a4b4c7d78` (20 passed, 2 timed/async failures in original full run).
- `b61-timed-fork-long-budget.log` — `a7c33b54621d977e33a9deffdea697749d5568ea41c29478deaa06953b397760`.
- `b61-async-fork-long-budget.log` — `cbe43a6149ca2f40811f35dad17a70d6aca31daa32c80ddd5245c02f50027c61`.
- `b61-retained-bytes-discriminator.log` — `64864e24d30d444eea7dd1bc835c21fcf7f09a627c5d76fd5eb5a7803d73898b`.
- `b61-retained-bytes-property-removal.log` — `3c4aaa78b60086621a9158d1790ab139540ca92cb32ba8074e603548a3a12dd5`.
- `b148-bound-import-wholefile.log` — `d3202bb701df8e7b3b5f4042227c32c77a2ff2fd90d06ee8c2dee0f828855560`.
- `b148-matched-admission-removal.log` — `3053e7de4ee217019cf163d5c3fd39d29b12127b5ec01d751be50e10cfb4f3a4`.

The exact target-tree denominator and absent evidence-file checks are recorded in [source-census.txt](r1-r2-review/source-census.txt). The only new local test run from this review was the focused validation-graph collection, and it errored before test execution. No heavy/numerical or broad suite was run.
