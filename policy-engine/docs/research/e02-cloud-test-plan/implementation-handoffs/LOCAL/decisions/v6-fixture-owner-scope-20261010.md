# V6 fresh-reader fixture ownership classification

Status: patch-only proposal; the target test file was not edited and no test was rerun. This closes a test-fixture custody mismatch, not the held V6 source-positive criterion.

## Finding and bucket

This is P40 **same class, one level deeper**: the producer-to-reader ownership binding was incomplete in the controlled fixture. It is not a new generation-status rule. P32/P38 apply: manifest tenant fields and content hashes are not the owner index. The property is that a tenant-scoped reader can resolve only a CAS artifact with a current matching tenant/cell owner claim. The divergent case is a manifest that declares `tenant-fixture/cell-fixture` while the owner index says `unowned`; the unscoped reader resolves it, but the request-scoped reader correctly refuses it.

The smallest repair is to construct the existing `FileSystemCAS` tenant view before the controlled profile/NCM/source/context writes, and pass that same store through the existing `_build_control_service(artifact_store=...)` seam. No owner-index rewrite, source-status weakening, or caller-asserted identity is involved. The patch retains the compiled source's producer result (`generation_unavailable`) and the separate child-profile limitation; its negative control tries that exact root N4 ref from a foreign tenant/cell view and expects the existing `ArtifactOwnershipError`.

## Source and retained discriminator

- Fixture producer: `tests/unit/runtime/http/test_control_service_di.py` `_run_controlled_simulate_only_job_fixture`, current SHA256 `74259e93e48ff7a654deebdac45f4b73d67ea1b562f846d5b3773df2a3fd74be`. The helper creates an unscoped store before `_configured_procurement_profile`; that helper persists NCM through the supplied store. The control service later receives that same store.
- Reader: `src/polisyos/runtime/http/routes/runs.py` `_candidate_simulation_projection` (around lines 741–932); it loads the root source through `GenerationSourceRepository` and converts any failed source verification to `not_established`.
- Loader: `src/polisyos/runtime/quality/generation_source.py` `GenerationSourceRepository.load` (around line 3613), which starts with `self.store.verify(ref)` and resolves bytes/manifest only after that succeeds.
- Owner enforcement: `src/polisyos/core/artifacts/store.py` `FileSystemCAS.for_tenant` and `_require_artifact_owner`; the unscoped producer did not record a tenant owner claim.

Raw retained source-bound probe: `LOCAL/raw/v6-fixture-owner-scope-original-location-20261010/reader_probe_v8.py` SHA256 `9593f73588bd07a108d330b66c21ffb40d4aa4049f82b1be515e67c9424d96ef`; full output `reader_probe_v8.log` SHA256 `fc494307bc5684f787f4b5572c64a5ae9bb3e54c60813a81feb431c406905709`. It reads the actual persisted `pro0` fixture's compiled artifact and source ref, runs the actual repository loader against both unscoped and `tenant-fixture/cell-fixture` stores, then calls the actual route projection with the scoped store. The exact command/launcher transcript was not retained, so argv is `not_established`; the script and complete output are retained.

The probe's decisive output is: unscoped `verify` and source load succeed, with source status `generation_unavailable`; tenant-scoped `verify` and source load raise `ArtifactOwnershipError` with `current owners: unowned`; the route projection retains the compiled ref but returns `n4_recursive_source_status=not_established`, `n4_recursive_source_result_status=null`, `n4_recursive_source_content_hash=null`, while the separate child profile remains `not_established` with `n4_recursive_source_generation_not_complete`. The run still has one candidate N5 observation. This confirms the route behavior is fail-closed and the defect lies in fixture producer custody.

## Proposed test delta

Unapplied patch: `LOCAL/raw/v6-fixture-owner-scope-original-location-20261010/v6-fixture-owner-scope.patch`, SHA256 `53fb77e5f3e2c8c3cb58de7765b6ff9048174c3580cad0f7855ccebbcd4c8c8e`. It changes only `tests/unit/runtime/http/test_control_service_di.py` (current target SHA remains the value above). The patch scopes the fixture store before profile creation; adds direct owner-bound load and foreign-scope refusal for the exact compiled `n4_recursive_source_ref`; and keeps the expected fresh GET source status `resolved` with `generation_unavailable` result. It does not touch the production reader or relax the foreign-scope guard.

The existing historical L2 confidence-negative remains separate: the candidate-scenario N5 source still asserts `historical_l2_confidence_withheld`, no forwarded confidence, and no credal reference. That root candidate-scenario path is not promoted to a recursive child source. Existing missing-source, N5 corruption, and sibling checkpoint controls are unchanged. The patch has not been applied or tested; style and behavior remain unverified.

This test repair proves owner-bound persistence/readback for the fixture only. It does not create an N4-derived child, and the actual recursive result remains `generation_unavailable`; V6 positive remains held pending an admissible actual child producer input.

Root continuation: the canonical copied patch above was applied after independent review. The two-test replay is retained in `raw/v6-owned-local-withholding-fresh-reader-verification-20261010`; both tests fail during fresh API initialization because unscoped PromotionRuntime tries to write an already-owned verifier-provenance artifact. This is the same custody class deeper in container construction. No PASS or V6 source-positive is claimed; the next patch must carry owner scope through the complete existing producer/reader construction seam.
