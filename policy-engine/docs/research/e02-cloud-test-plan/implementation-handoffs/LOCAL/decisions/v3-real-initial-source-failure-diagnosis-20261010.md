# V3 real initial-source and projection failure diagnosis

## Decision

The retained composed run has two independent defects and both need bounded repairs. The first natural-language job fails before route publication because the fixture producer writes its substrate registry to CAS without tenant/cell ownership. Five source-backed missing-epoch controls reach the existing native readback error but escape before the service's established typed-refusal boundary. The unapplied candidate in `LOCAL/raw/v3-real-initial-source-failure-diagnosis-20261010/candidate-unapplied.patch` repairs the fixture producer and widens one existing exception boundary. It also proposes real list/detail GET controls over the same produced route and selected receipt.

This is a patch proposal only. No product/test source was edited, no test was run for the proposed delta, and no pass/closure is claimed.

## Exact run and current red

The source-bound command is in `LOCAL/raw/v3-real-initial-source-verification-20261010/command.json`. It ran the served acquisition test, the acquisition-world-growth unit module, and the full `test_acquisition_world_growth_chain.py`, with `--basetemp=_build/e02-repair-fixtures/v3-real-initial-source-verification-20261010`. The retained JUnit is `.../LOCAL/raw/v3-real-initial-source-verification-20261010/junit.xml@2a17e53ac20ae6337ea46f152f14572d9e9783b2857d00c4a2b2f6812b12fc91`; captured stdout is `.../stdout.txt@6189e2dc20de15573eee066ca470008ff01d9c02d4fff37f3e043d1822ba79da`, stderr `.../stderr.txt@d1f768f510c26aea0fb8d55a00b95ff34851c1ca66fadb20e807732a22c5cebc`. Result: 22 collected, 16 passed, 6 failed, exit 1. These are retained original run outputs, not a rerun after this proposal.

The five shared-projection failures are:

- `test_actual_wdi_admits_delta_and_reenters_same_case[False]`: `basis_mismatch`, activated epoch receipt `sha256:670764459582849f71f1815e8c0908692f46f953a67a95570d2e37a83c71fb5d` not found.
- `test_actual_wdi_admits_delta_and_reenters_same_case[True]`: `basis_mismatch`, receipt `sha256:034026de5e117dbf2f9471df9459280d495c63c9c8b5b7e57ee50c1125d41458` not found.
- `test_active_dataforge_row_builds_limited_candidate_world_with_source_time_unknown`: receipt `sha256:8a049912a5206f424fadc42d2fd71e9b4fe6ee563ede3be51ed900d72e261305` not found.
- `test_served_wdi_admits_selected_row_but_n5_refusal_prevents_n8`: receipt `sha256:864a94a7ff9cfa1d8bc9d84c40da470d20715d36c0acde133ca427c143ad6892` not found.
- `test_real_value_owner_gateway_projects_selected_wdi_iso3_row_into_iso2_profile`: receipt `sha256:a769e6c91079444ea25beb33010a8ee9cfaea326b3e1d60a23d4791deb0f2a2a` not found.

Each is `SemanticEpochAdmissionResolutionError: basis_mismatch: activated epoch readback: Artifact not found`. The shared helper already exercises a real positive projection (`admitted_observation_delta == 1`) before removing the selected CAS blob, then expects the existing `acquisition_native_admission_unverified` code; see `tests/integration/core_runtime/test_acquisition_world_growth_chain.py@9a1b1004519904f306e3b7a57116316081e1da916d33e5e70ca486f696fce742`, around its `_projection` missing-blob control. The five failures are one shared-boundary defect, not five behavior-specific failures.

The separate served-job failure is job `053af6e9cec64224b4cbd781104975d4`, run `R_df9bbcbcebac040a`, state `failed`: `candidate_simulation_substrate_registry_custody_unverified` for registry `sha256:40e131e8c392b1bf340d122b0ed3a7a2d16e63984f9fbe8d3e0166ed82781278`, current owner `unowned`. The successful read-only snapshot is captured in `.../LOCAL/raw/v3-real-initial-source-failure-diagnosis-20261010/job-owner-snapshot.json@311de9a8154c61a2ebec5b47309cc1cbf72e71645b0103ee00bd33bab93f0d04`, produced by `job-owner-snapshot-reader.txt@c5d13145f944c98a0834cc1932a599b131f6274ae5016f1670de63217ada8bca` with command metadata `job-owner-snapshot-command.json@f57b139bad1264074f8f40dbe56d43a1523c477fb5bf906f664fac744375d4b7` (exit 0; empty stderr `@e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). The registry blob exists and its SHA matches the content-addressed ID, but no ownership generation claims it. The natural-language job does not complete, so initial-source completion is not established by this run; the saved row alone does not establish how far N4/N5 progressed.

## Current source property and narrow delta

Current preimages at candidate HEAD `9194a65fb59355ceac35270c869f429efc7482d8`:

- `src/polisyos/runtime/http/services/acquisition_action_service.py@b5162adc207e9bb1ebae3fed6c7135bd4f29f8b89dddfa2af08c3166ddc59fde`
- `tests/integration/core_runtime/test_acquisition_authority_served.py@8e1c8b13612ca9bac0443b4a46ef238bb81fcf2e6d81cc5959f96fdd1e6869cf`
- Existing shared negative helper: `tests/integration/core_runtime/test_acquisition_world_growth_chain.py@9a1b1004519904f306e3b7a57116316081e1da916d33e5e70ca486f696fce742`

In `_projection`, `execution_ready = _production_execution_bridge_ready(closure)` runs before the existing `try`, while only `project_world_growth` is inside it. The latter already maps `SemanticEpochAdmissionResolutionError`, `ValueError`, and `OSError` to the correct existing `AcquisitionActionServiceError("acquisition_native_admission_unverified")`. Move readiness into that same try so a present selected ref whose CAS readback fails retains the same semantic refusal and cause. This is the minimum structural fix for all five controls.

The protected prepare/reservation sibling `_require_production_execution_bridge` also calls `prepare_route_execution`, which calls `require_route_ready`. The proposed delta maps the same native-admission failure family there, preserving the original cause. It explicitly rethrows existing `AcquisitionActionServiceError` first (including `acquisition_live_attempt_exhausted`) and keeps `LiveAcquisitionExecutionError.code`; it does not relabel absent work, exhausted attempts, or other existing refusal codes as an admission-integrity failure. Supporting source readback: `src/polisyos/runtime/http/services/acquisition_surface_execution.py@613c3812f91f44c86c8a10fec1e14a84c36faaef69e1d8da1299fb22b3035a08`.

The test fixture calls `_served_wdi_candidate_profile` inside `_within_fixture_owner`/`tenant_scope`, but constructs `FileSystemCAS(cas_root)` with no owner-enforcement flag. `FileSystemCAS` defaults ownership enforcement to `tenant_id is not None`; see `src/polisyos/core/artifacts/store.py@f787817462174c52d3ffdce9586d74a1c42276af8f38fae08d73c5f8bb7beec2`, constructor around line 474. The candidate explicitly sets `ownership_enforced=True` on that fixture store so registry and dependent artifacts are actually owned by the active tenant/cell. It does not weaken the production verification predicate or retrofit ownership claims after writing.

The candidate adds actual public route-list and route-detail GET checks on the served route. It first requires both to return the activated route and the admitted delta. Then it probes both a missing blob and bytes that fail CAS digest verification for the selected, already-persisted overlay admission receipt (keeping the reference and manifest), GETs both endpoints for each invalid state, and restores the original bytes in `finally`. The required result is HTTP 409 with the existing `acquisition_native_admission_unverified` code on both surfaces. Existing route mapping is `AcquisitionActionServiceError -> conflict` in `src/polisyos/runtime/http/routes/acquisitions.py@21ad3921baac76a30fbe85d1f60338920ab1472646d25c256cdef794bc47f36e`; the runtime error handler preserves its code in `src/polisyos/runtime/http/errors.py@bdbdc71b506420b0beae77a186066cecd7cfa52cee614eca38d4f61b88580ba6`.

Candidate patch: `.../LOCAL/raw/v3-real-initial-source-failure-diagnosis-20261010/candidate-unapplied.patch@d5d028c1ce26592492351f092b9173465b65aa09102f35016450edfaa82a2d79` (5,295 bytes). It targets only the two current preimage files above. No product/test file was written by this investigator.

## P40 and verification boundary

- **NEW_CLASS — fixture ownership production.** This is the source/root/profile ownership predicate for persisted source artifacts. The discriminating evidence is the actual failed first job and unclaimed registry in the read-only snapshot. The closing invariant is that this fixture writes through an ownership-enforced CAS while in its established tenant/cell scope. It is not a projection error and should not be folded into the exception handler.
- **SAME_CLASS_DEEPER — selected-ref admission readback at public projections.** Five independent consumers share the same readiness/project-growth catch gap. Stop patching by test. Widen the existing typed refusal boundary to include the whole readiness-plus-projection operation and exercise both real GET projections with the same persisted selected ref and removal control.

Relevant register patterns: P29 (actual property tests rather than markers), P31 (one structural boundary repair rather than per-consumer edits), P38 (the code tests only the later projection failure path while the property spans readiness and projection), and P40 (the five removals are one deeper escape of the same class). The route status remains fail-closed; the proposal does not turn missing or malformed admission evidence into `producer_missing`, `no_growth`, or a successful projection.

First discriminating verification after root reviews/applies the patch: rerun those five exact failing selectors; run the served integration test (it contains the new real list/detail GET positive and removal negative); retain the existing `_projection` positive-then-removal test in the whole chain module to ensure both direct helper and public API remain covered. Full composed R1 replay remains required by the owner; this proposal has not run it. No claim is made that either failure class is closed until those actual outputs are captured.
