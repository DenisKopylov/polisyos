# FWC-01 — finite-window completeness for diagnostic-event consumers

**Status:** candidate inherited/latent engineering task; not a confirmed R15 regression. Do not begin implementation before the required R, H, and N work is complete and the P41 four-base replay is recorded.
**Evidence receipt:** `/Users/deniskopylov/.codex/scratch/e02-r2-cycleboard-denominator-audit-20260924.md@sha256:95584f99da20551965c71a5682db2a0b61f43f823cb05e7a39b1096d2b1b1dee`.
**Semantics review:** `/Users/deniskopylov/.codex/scratch/e02-r2-fwc-partial-semantics-review-20260924.md@sha256:9fbe2fe3aa184d0d244c7776456293a9d941f719e8a3ed8b436385c1ade8cc30`.
**Attribution:** inherited/latent. `AcquisitionRouteLoop` and `ControlPlaneStore.list_diagnostic_events` have the same relevant implementation on E02 base, E02 head, main, and Phase0. CycleBoard movement projection was added on main by `3ce7d9c5a1766a38b91947a15f9ed3b36d3d5f3b`; it is not E02-introduced. No P41 test attribution has been run or inferred.

## Property and production callers

A separately qualified, exact `MovementRecord` may be surfaced as a positive about that individual receipt even while its event scan is incomplete. Incompleteness limits claims about the collection, not the qualified record. Keep positive evidence and scan coverage as separate typed facts: a positive plus an incomplete scan is visibly `partial`; a completed positive is `available`; no positive is `not_established`, with an explicit incomplete-scan limitation when the scan did not complete; malformed or custody-invalid evidence remains `invalid_source`. An incomplete scan cannot establish absence, the only/latest movement, complete history, row enumeration, or register closure.

RouteLoop has a stricter uniqueness obligation. It must scan through the owner’s query high-water mark before returning a unique terminal event or constructing `VerifiedAcquisitionRouteClosure`: a second matching terminal event on a later page changes the result to ambiguous. A page-budget stop after observing one match is typed incomplete, not a verified closure.

The existing owner `ControlPlaneStore.list_diagnostic_events` defaults to 500 rows and clamps to 1,000, orders by ascending `row_id`, and exposes no cursor, high-water mark, or `has_more` signal. Two production consumers have broad scans:

- `AcquisitionActionService._resolve → AcquisitionRouteLoop.resolve_current_route → _resolve_terminal_event` omits `limit`, then filters the first 500 run/job rows. A terminal event after row 500 can be reported missing; a later second match after a page-one match can also be hidden while the prefix appears unique.
- `RuntimeContainer → CycleBoardProjectionService._compose → AcquisitionMovementService.project_row → GET /api/v1/exports/governed-projections/depth-n-cycle-board` asks for the first 1,000 run rows. Today, `len(rows) >= 1000` causes `invalid_source` / `movement_event_window_incomplete` and skips all rows. That refusal is visible in the served source manifest/dashboard, not silent. It also refuses an exactly complete set of 1,000 and withholds a valid matching movement in a saturated window.

## Owner-first capability plan

Extend the existing `ControlPlaneStore` and `RuntimeDiagnosticEventLog` query owner with stable append-order pagination, a query-start high-water mark, and owner-recomputed completion/continuation for the exact scope. The high-water mark defines what “complete” means while later events append. Keep one owner; do not infer completeness from a page length or merely increase the hard cap. Review backend parity and snapshot semantics before implementation.

CycleBoard should continue through available pages within its declared work budget, collecting exact individually admitted records. Add a strict `scan_completeness` (`complete` / `incomplete`) and as-of high-water/query receipt to `MovementRowProjection` and the `native-movement:<row_id>` composition source. Keep positive evidence and scan coverage as separate typed facts: if the budget ends before completion, retain qualified records and surface the row/source tier as `partial` with the incomplete scan and watermark; do not put an absence reason beside a positive. Once the owner confirms completion, records yield `available`; no matching record yields `not_established`; malformed or custody-invalid evidence remains `invalid_source`. Keep source `availability` about the positive evidence and expose coverage separately. The dashboard row presenter currently drops row `movement_status`, so carry the partial limitation to both the row and source card. Keep CycleBoard `exhaustive=False`; its movement source remains unusable for row enumeration, global growth, or register closure. Its aggregate gap status cannot say `admitted` while a row scan is incomplete.

RouteLoop must continue to the same high-water completion even after the first eligible terminal event. Only a complete scan with exactly one eligible event can resolve uniquely; multiple matches remain ambiguous. A budget stop yields a typed incomplete result and cannot produce `VerifiedAcquisitionRouteClosure`.

No principal-level decision is required for this narrow positive-plus-coverage contract. The event-store owner should settle the cursor and DTO names as an implementation contract before coding. A principal decision would be needed only to let incomplete scans authorize a protected action, establish absence/uniqueness/currentness of a whole set, or close GY-GAP6/DS15; this task does none of those.

If coverage is added to a hashed CycleBoard packet or projection manifest, bump the applicable schema/projection-rule version and retain historical serializers that exclude the new fields. Regenerate OpenAPI/runtime-client surfaces only through their owners and inspect each generated delta.

## Boundary probes required

All probes are behavioral through the served consumers and owner query. Keep exact tenant, cell, run, job, row, design-problem, phase, and artifact-reference checks.

| Consumer | Complete positive | Complete negative | Removal probe (markers retained) | Property-preserving control |
|---|---|---|---|---|
| RouteLoop, page size 500 | Exactly 500 rows, one eligible terminal at row 500, and owner-complete high-water resolves uniquely. At 501 rows with one eligible terminal at row 501, a complete two-page scan resolves uniquely. | Exactly 500 rows with no eligible terminal reports `source_terminal_event_missing` only after completion. At 501 rows with no eligible terminal it reports the same true absence only after page two. Wrong-tenant/cell/compiled-ref/manifest-ref events are not eligible. | Keep cursor/completion markers but disable advancement or falsely mark page one complete. Put one eligible terminal at row 500 and a second at row 501: with a two-page budget the served resolver must report ambiguous, not unique. Separately, with the only eligible event at row 501, it must find it or report incomplete, never report complete absence. | A small complete set with one eligible event resolves; a complete set with duplicate eligible events remains ambiguous. |
| CycleBoard, page size 1,000 | Exactly 1,000 rows with valid movement at row 1,000 and owner-complete status projects `available`. With 1,001 rows and valid movements at rows 1,000 and 1,001, a two-page complete scan returns both records as `available`. If a one-page budget stops after a valid row-1,000 record while `has_more` is true, surface that record as `partial` with `scan_incomplete`, not unavailable or complete. | Exactly 1,000 complete events with no matching movement returns `not_established`. At 1,001 rows with no match, a one-page stop returns `not_established` plus `scan_incomplete`; only a completed scan establishes no match. Foreign tenant/cell/row/run/design-problem evidence never becomes a positive. | Keep continuation markers but disable page advancement. With a two-page budget, row 1,000 and row 1,001 both contain valid movement: the served result must not claim complete or omit the later record. Separately, put the only valid movement at row 1,001: a complete two-page scan finds it; a one-page budget reports incomplete, never complete absence. | A small complete set with one exact admitted record remains `available`; a small complete set with none remains `not_established`; wrong bindings never become positive; malformed/custody-invalid source stays `invalid_source`. |

At an explicit budget stop, CycleBoard may surface an exact individually qualified positive as `partial`, while preserving the independent incomplete coverage field. Without a positive it remains `not_established` plus `scan_incomplete`. A completed no-match is `not_established` without that limitation. RouteLoop may retain an observed match for diagnostics, but no incomplete scan may be treated as unique or produce verified closure. Test positive, negative, wrong-binding, duplicate, malformed, and later-page cases; do not pin only markers or field names.

## P37 / P38

- **P37 predicate:** currently `not_established`. The store returns a prefix and its row count but does not establish whether more matching rows exist. Completion must be recomputed by the owner for the exact query scope and high-water mark, not supplied by a caller assertion.
- **P38 divergence:** `len(rows) >= 1000` treats an exactly complete CycleBoard population as incomplete and discards a qualified positive. A saturated CycleBoard prefix cannot establish absence or complete history. RouteLoop treats a no-match over 500 rows as missing and a single match over 500 rows as unique, either of which can be contradicted by a later page.
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

Expected source write set: `runtime/http/services/control_plane_store.py`, `runtime/quality/event_log.py`, `runtime/quality/acquisition_route_loop.py`, `runtime/quality/acquisition_movement.py`, `runtime/http/services/cycle_board_contracts.py`, the CycleBoard projection/presentation path, and behavioral tests above. If hashed schema/projection fields change, include versioned historical serialization plus generated OpenAPI/runtime-client files through their owners; inspect every generated delta.

Use the single integration writer and record the file lease before implementation. `control_plane_store.py` overlaps R8’s guarded-store/lease work; `acquisition_route_loop.py` and `acquisition_movement.py` overlap R13’s acquisition/custody work. Sequence FWC-01 with those classes; do not race edits or tests that mutate shared generated artifacts. Re-run the complete test-file denominator after any shared-file change. The event log is a shared source owner; no duplicate store/query is acceptable.

## Acceptance criteria

1. The owner API reports complete versus incomplete for a stable query scope and as-of watermark; page continuation neither skips nor duplicates events, including with later appends.
2. CycleBoard preserves exact individually admitted positives during an incomplete scan as `partial` with distinct typed coverage; the two-page 1,001-row case completes all available work and returns the full set; no positive plus incomplete scan never becomes a complete absence claim.
3. RouteLoop scans through completion after the first match; only one match in a complete high-water set resolves; a later second match stays ambiguous; budget exhaustion never produces a unique verified closure.
4. Exact 500/501 and 1,000/1,001 positive, negative, removal, and control probes pass through production composition paths; malformed evidence and wrong identity bindings retain their refusals.
5. A whole-file four-base replay after changes shows no new pass→fail outside any separately approved decision; served tests exercise producer/query/projection rather than DTO construction alone.
6. CycleBoard keeps `exhaustive=False`, does not claim global growth or register closure, exposes the partial limitation in the row and source card, and cannot label aggregate movement `admitted` while a row scan is incomplete.
7. Any hashed projection/schema extension has a version bump and byte-exact historical serializer; generated owners verify and their complete deltas are reviewed.

## Crosswalk and residual uncertainty

This advances DS15 acquisition routes and its CycleBoard/GY-GAP6 movement surface, with adjacent GY Phase 5/6 and N13b consumers. It does not close catalog-bound acquisition, positive production world growth, or the GY/Atlas plan tasks. The exact per-row receipt/date → same DesignProblem/cycle re-entry → deeper terminal chain remains the authority-bearing boundary; an incomplete scan cannot imply world-model write-back. Relevant source plans: `policy-engine/docs/plans/active/atlas-slices/DS15-acquisition-routes.md@ccc4a7bd817f43b8053e88a86f9ec0cc4ccc7c42`; `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@9d510e2ee43fd017028542f180008cd2c2aacb37`.

Unresolved: no production run/job cardinality scan was performed; it is not established that any caller has reached 500 or 1,000 events. The source audit established code reachability of both callers, not reachability of these thresholds in production. Record any later read-only cardinality census with its complete denominator and production-data manifest reference. This proposal does not report an incident or claim a confirmed regression.
