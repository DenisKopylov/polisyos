# Independent review: V3 real initial-source failure repair

## Verdict

**Static GO to apply and run the focused verification; not a closure claim.** I reviewed the exact final candidate at `LOCAL/raw/v3-real-initial-source-failure-diagnosis-20261010/candidate-unapplied.patch`, SHA-256 `d5d028c1ce26592492351f092b9173465b65aa09102f35016450edfaa82a2d79` (5,295 bytes). The earlier `959ba…c2a85d6` identifier was a superseded draft; this review does not cover that unavailable draft. The retained decision note records the same final `d5d028…` digest.

The candidate modifies only:

- `src/polisyos/runtime/http/services/acquisition_action_service.py`, whose current bytes match preimage SHA-256 `b5162adc207e9bb1ebae3fed6c7135bd4f29f8b89dddfa2af08c3166ddc59fde`.
- `tests/integration/core_runtime/test_acquisition_authority_served.py`, whose current bytes match preimage SHA-256 `8e1c8b13612ca9bac0443b4a46ef238bb81fcf2e6d81cc5959f96fdd1e6869cf`.

No source or test edits were made for this review, and I did not run tests or processes.

## Why the delta fits the observed failures

In `_projection`, `_production_execution_bridge_ready` calls `require_route_ready`, which can revalidate the already-selected epoch receipt and raise `SemanticEpochAdmissionResolutionError`. The current code invokes readiness before the `try`, while the later `project_world_growth` call already translates that error, `ValueError`, and `OSError` to `acquisition_native_admission_unverified`. Moving readiness into that existing boundary closes the shared escape for the five retained missing-blob failures without changing the projection result or turning a supplied-but-unreadable ref into absence/no-growth.

The candidate makes the same translation at the public reservation check. It explicitly re-raises existing `AcquisitionActionServiceError` and preserves `LiveAcquisitionExecutionError.code`, so the existing action/exhaustion refusals are not relabeled. One boundary caveat for execution review: `prepare_route_execution` includes both read-only `require_route_ready` and lease reservation. Thus a raw `OSError` occurring during lease creation/fsync can receive the admission-unverified code too; that remains fail-closed, but it is a broader reason mapping than an error known to arise from CAS readback. The requested focused run should retain the existing exhaustion/action controls and report the resulting code accurately.

## Producer and consumer witnesses

The fixture already calls `_served_wdi_candidate_profile` under `_within_fixture_owner`, which installs the concrete tenant and cell. Its CAS constructor omitted `ownership_enforced=True`; the store defaults ownership enforcement off when constructed without an explicit tenant. Setting that option makes fixture writes record the active owner at creation, repairing the observed unowned registry at the producer rather than weakening the read-side predicate or retroactively claiming ownership.

The new checks are on the actual served run. They require route list and detail GETs to return the activated route and admitted delta, then remove and digest-corrupt the selected receipt blob in turn while keeping the reference/manifest, requiring both GETs to return 409 with `acquisition_native_admission_unverified`. The original bytes are restored in `finally`. This exercises the public projections through their real `_resolve`/`_projection` path; it is stronger than a helper-only or marker test. The direct helper test already has a positive projection followed by selected-blob removal, providing a second consumer boundary.

## P40 and remaining boundary

- **NEW class:** fixture producer ownership. The distinguishing fact is the persisted unclaimed registry despite the fixture's active tenant/cell scope. The proposed explicit owner-enforced store closes that producer-side gap.
- **Same class, one level deeper:** selected epoch readback across readiness and projection. The five failures converge on one exception boundary, so the structural move is preferable to per-consumer patches. Both public GET projections get positive, missing-byte, and corrupt-byte checks.

The retained baseline is 22 tests, 16 passing and 6 failing, including the five shared receipt-readback escapes and one unowned fixture registry. It is evidence of the current red, not evidence that the proposed patch passes. Next required evidence is the exact five failing selectors plus the served integration test and existing direct helper control, with complete outputs. A successful focused run would close only these bounded projection/fixture defects; it would not establish the entire composed V3 or R1 workflow.
