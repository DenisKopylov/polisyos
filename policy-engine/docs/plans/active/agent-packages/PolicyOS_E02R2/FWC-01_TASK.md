# FWC-01 — finite-window completeness for diagnostic-event consumers

**Status:** candidate engineering task; not a confirmed R15 regression and not authorized implementation scope yet.
**Evidence receipt:** `/Users/deniskopylov/.codex/scratch/e02-r2-cycleboard-denominator-audit-20260924.md@sha256:95584f99da20551965c71a5682db2a0b61f43f823cb05e7a39b1096d2b1b1dee`.
**Attribution:** inherited/latent. `AcquisitionRouteLoop` and `ControlPlaneStore.list_diagnostic_events` have the same relevant implementation on E02 base, E02 head, main, and Phase0. CycleBoard movement projection was added on main by `3ce7d9c5a1766a38b91947a15f9ed3b36d3d5f3b`; it is not E02-introduced. No P41 test attribution has been run or inferred.

## Property and production callers

A consumer that decides whether a route terminal event or row movement receipt exists must inspect the complete relevant event set or carry an explicit incomplete result. A bounded append-order prefix must not become either a complete set or a claim of absence. Exact tenant, cell, run, job, phase, artifact-reference, and movement-row bindings remain required; the board remains non-exhaustive for row enumeration and register closure.

The existing owner `ControlPlaneStore.list_diagnostic_events` defaults to 500 rows and clamps to 1,000, orders by ascending `row_id`, and exposes no cursor, high-water mark, or `has_more` signal. Two production consumers have broad scans:

- `AcquisitionActionService._resolve → AcquisitionRouteLoop.resolve_current_route → _resolve_terminal_event` omits `limit`, then filters the first 500 run/job rows. A matching terminal event after row 500 can become `source_terminal_event_missing`, with no truncation reason.
- `RuntimeContainer → CycleBoardProjectionService._compose → AcquisitionMovementService.project_row → GET /api/v1/exports/governed-projections/depth-n-cycle-board` asks for the first 1,000 run rows. `len(rows) >= 1000` causes `invalid_source` / `movement_event_window_incomplete` and skips all rows. This refusal is visible in the served source manifest/dashboard, not silent; it also refuses a complete set of exactly 1,000 rows and withholds valid matching movement in a saturated window.

## Owner-first capability plan

Extend the existing `ControlPlaneStore` and `RuntimeDiagnosticEventLog` query owner with complete, stable pagination (for example, an append-order keyset cursor plus a query-start high-water mark and truthful continuation/completion state). The high-water mark makes “complete” mean complete as of one bounded read while new events are appended. Consumers continue until their exact discriminator is found or that read is complete; if a declared work budget ends first, they preserve a typed incomplete result rather than report absence. Keep one owner and do not merely increase the hard cap. Review backend parity and transaction/snapshot semantics before implementation; do not create a parallel event store.

No principal-level choice or exception to an existing lean is identified. The event-store owner should settle the cursor/API shape as an implementation contract before coding.

## Boundary probes required

All probes are behavioral and must run through the served consumers as well as the owner query. Preserve the exact identity checks in every vector.

| Consumer | Complete positive | Complete negative | Removal probe (markers retained) | Property-preserving control |
|---|---|---|---|---|
| RouteLoop, page size 500 | Exactly 500 rows with the eligible terminal transition at row 500 resolves. At 501 rows, the eligible transition at row 501 resolves after continuation. | Exactly 500 rows with no eligible terminal event returns `source_terminal_event_missing` only after the owner reports complete. At 501 complete rows with no eligible event it returns the same true-absence result after page two. A wrong-tenant/cell/compiled-ref/manifest-ref event is not a positive. | Keep cursor/completion marker fields and event content unchanged, but disable page advancement or falsely mark page one complete. With the eligible terminal only at row 501, the served route-resolution test must turn red (must fail to resolve the exact source or report incomplete, never silently pass as a complete negative). | An ordinary set below 500 with one correctly bound terminal remains resolved; duplicate eligible terminals remain ambiguous. |
| CycleBoard, page size 1,000 | Exactly 1,000 complete run events with valid matching movement at row 1,000 projects `available`. At 1,001 rows with the valid movement at row 1,001, continuation finds it and projects `available`. | Exactly 1,000 complete events with no valid matching movement returns `not_established`, not `invalid_source`. A complete 1,001-event set with no valid match also returns `not_established` after continuation. A foreign tenant/cell/row/run/design-problem binding never satisfies the row. | Keep pagination markers and event fixtures, but disable continuation or claim page one complete. With 1,001 events and the only valid movement at row 1,001, the served CycleBoard test must turn red; no valid movement may be hidden behind a page-one “complete” claim. | A valid movement in a complete set below 1,000 (including a 999-event boundary control) remains available. Malformed source evidence remains `invalid_source`; the board still cannot claim row-set exhaustiveness. |

An incomplete scan stopped by an explicit budget must remain distinguishable from true absence: CycleBoard should retain its typed incomplete refusal (`invalid_source` with `movement_event_window_incomplete`, or a source-owner-approved equivalent) and RouteLoop must not call it `source_terminal_event_missing`. A complete no-match remains `not_established` for CycleBoard or `source_terminal_event_missing` for RouteLoop. Test positive, negative, wrong-binding, duplicate, and malformed cases; do not pin only constants or field names.

## P37 / P38

- **P37 predicate:** currently `not_established`. The store returns a prefix and its row count but does not establish whether more matching rows exist. An owner-recomputed completion signal must be tied to the same query scope and high-water mark, not supplied by a caller assertion.
- **P38 divergence:** `len(rows) >= 1000` calls an exactly complete CycleBoard population incomplete; absence of a matching movement in a saturated prefix does not establish absence. RouteLoop’s no-match over its default 500 rows calls a truncated prefix missing. These are the exact boundaries the current gates are intended to police.
- **Pattern pass:** reuse the event owner (P27); enumerate the complete source denominator (P35); verify the true completeness predicate rather than a prefix proxy (P37/P38); make removal probes behavioral (P29); avoid per-consumer cap patches (P31).

## Four-base P41 prerequisite

Before implementation, replay every file below at E02 execution base `78187878e`, E02 head `00d946c2b`, main `5fd3ebcc1`, and the then-current integration head, with the same environment and production-data link. Capture per-test outcomes; do not infer regression ownership from source history alone. This is the complete direct event-call test set plus the route/movement/served-surface set identified by the audit; overlapping paths need run only once per base.

- `policy-engine/tests/integration/core_runtime/test_acquisition_admission_bundle.py`
- `policy-engine/tests/repo_quality/tools/test_runtime_resilience_matrix.py`
- `policy-engine/tests/unit/runtime/http/services/test_evaluation_safety.py`
- `policy-engine/tests/unit/runtime/http/test_acquisition_route_authority_sink.py`
- `policy-engine/tests/unit/runtime/http/test_control_plane_store.py`
- `policy-engine/tests/unit/runtime/http/test_human_decision_service.py`
- `policy-engine/tests/unit/runtime/http/test_runtime_authorization_access_audit.py`
- `policy-engine/tests/unit/runtime/quality/test_agent_action_authority.py`
- `policy-engine/tests/unit/runtime/quality/test_authority_reconciliation.py`
- `policy-engine/tests/unit/runtime/quality/test_crash_retry_partial_state.py`
- `policy-engine/tests/unit/runtime/quality/test_runtime_event_log.py`
- `policy-engine/tests/unit/runtime/quality/test_acquisition_route_loop.py`
- `policy-engine/tests/unit/runtime/quality/test_acquisition_movement.py`
- `policy-engine/tests/unit/runtime/quality/test_acquisition_movement_positive.py`
- `policy-engine/tests/unit/runtime/http/test_cycle_board_movement.py`
- `policy-engine/tests/unit/runtime/http/test_cycle_board_projection_service.py`
- `policy-engine/tests/unit/runtime/http/test_runtime_api_contract_hardening.py`
- `policy-engine/tests/unit/runtime/http/test_governed_projection_api.py`
- `policy-engine/apps/runtime-dashboard/src/features/runs/components/cycleBoardPresentation.test.ts`
- `policy-engine/apps/runtime-dashboard/src/features/runs/api/acquisitionRouteCompatibility.test.ts`

No tests have been run for this proposal. Do not start implementation until the parent lane’s required R, H, and N work is complete and the P41 broker has recorded these four-base baselines. If a relevant red is inherited, record its owner and proceed; if it is new, classify it before carrying it.

## Write set, leases, and coordination

Expected source write set: `runtime/http/services/control_plane_store.py`, `runtime/quality/event_log.py`, `runtime/quality/acquisition_route_loop.py`, `runtime/quality/acquisition_movement.py`, plus behavioral tests in the list above. A CycleBoard status/schema change may add `runtime/http/services/cycle_board_contracts.py`, OpenAPI/runtime-client generated families through their owners, and the dashboard presentation/component/tests; admit those files to P41 before touching them.

Use the single integration writer and record the file lease before implementation. `control_plane_store.py` overlaps R8’s guarded-store/lease work; `acquisition_route_loop.py` and `acquisition_movement.py` overlap R13’s acquisition/custody work. Sequence FWC-01 with those classes, do not race edits or tests that mutate shared generated artifacts, and re-run the complete test-file denominator after any shared-file change. The event log is a shared source owner; no duplicated query/store implementation is acceptable.

## Acceptance criteria

1. The owner API can report complete versus incomplete for a stable query scope and as-of watermark; page continuation neither skips nor duplicates events across the two storage pages, including with later appends.
2. RouteLoop and CycleBoard pass the exact 500/501 and 1,000/1,001 positive, negative, removal, and control probes above through their production composition paths.
3. True absence, malformed evidence, ambiguous duplicates, and wrong tenant/cell/run/job/ref binding retain their existing distinct refusal/ambiguity behavior; a page-budget stop never masquerades as absence.
4. A whole-file four-base replay after changes shows no new pass→fail outside any separately approved decision; the served consumer tests exercise event production/query/projection, not just query DTO construction.
5. CycleBoard keeps `exhaustive=False` and its source cannot be used to claim row enumeration, global growth, or register closure.

## Crosswalk and residual uncertainty

This advances DS15 acquisition routes and its CycleBoard/GY-GAP6 movement surface, with an adjacent GY Phase 5/6 and N13b consumer relationship. It does not close catalog-bound acquisition, positive production world growth, or the GY/Atlas plan tasks. Relevant source plans: `policy-engine/docs/plans/active/atlas-slices/DS15-acquisition-routes.md@ccc4a7bd817f43b8053e88a86f9ec0cc4ccc7c42`; `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@9d510e2ee43fd017028542f180008cd2c2aacb37`.

Unresolved: no production run/job cardinality scan was performed; it is not established that any caller has reached 500 or 1,000 events. The source audit established code reachability of both callers, not reachability of these thresholds in production. Record any later read-only cardinality census with its complete denominator and production-data manifest reference. This proposal does not report an incident or claim a confirmed regression.
