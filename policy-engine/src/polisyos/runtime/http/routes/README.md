# Runtime HTTP Routes (`polisyos.runtime.http.routes`)

`runtime.http.routes` is the thin HTTP wiring layer for runtime API v1. The route modules only
translate requests to service calls, set authz context, and return contract-backed DTOs.

## Role in System

- **Depends on:** `runtime.http.services`, `core.contracts.runtime`, and `core.security` helpers.
- **Used by:** the FastAPI app in `runtime.http.app`.
- **Boundary function:** keeps route handlers small and pushes business logic into services.

## Key Concepts

- **Health routes** - liveness and readiness checks.
- **Runs routes** - run listing, details, timeline, lineage, nodes, and workflow surfaces.
- **Debug routes** - node, governance, errors, feedback, and compare views.
- **Artifacts routes** - manifest, content, lineage, and schema inspection.
- **Control routes** - run launch, feedback/reissue, data, and Lex control-plane entrypoints.
- **Human-decision routes** - run-bound pre-action gates, step-up-protected decision
  writes, exact evidence delivery, and review-effectiveness projection. The routes
  consume deployment-verified service results; request DTOs never carry authority.
- **Governed projection routes** - retain the generic dynamic-ID read surface and add
  one static-before-dynamic confidence-ledger risk-spend GET. That specialized
  operation is reviewer-protected with tenant-collection binding and is its
  guarded source's sole HTTP surface.
- **Epoch-validity batch intake** - accepts only a transition artifact ref and requested query
  context. Status, targets, dependency keys, dedupe values, and verifier identity are resolved by
  the container-owned Decision Validity service rather than accepted from HTTP callers.
- **Acquisition routes** - expose run-bound costed-route GETs under
  `RUNS_REVIEW`/tenant-collection binding and decision/execute POSTs under the
  existing `EVIDENCE_ACQUIRE` request-composite binding plus acquisition
  step-up. Route facts and lifecycle status are server projections; callers may
  only echo the strict replay pins used for optimistic concurrency.

## Public API

- route modules: `health.py`, `runs.py`, `debug.py`, `artifacts.py`, `control.py`,
  `human_decisions.py`, `acquisitions.py`, `governed_projections.py`
- route routers exported from `__init__.py`: `health_router`, `runs_router`,
  `debug_router`, `artifacts_router`, `control_router`, `human_decisions_router`,
  `acquisitions_router`

## Current State

- Last updated: 2026-08-29
- The control-plane surface still includes the broader data/lex endpoints documented in the current routes.
- `openapi_contract.py` now mirrors new control and decision-validity examples that sit behind these routes.
- Completed human-decision exposure receipts are appended only by the dedicated
  exact-byte response path in the existing access-audit trail; generic artifact
  reads and generic audit appends cannot mint them.

## Run-bound predictive-calibration routes

The runs router also exposes GET /api/v1/runs/{run_id}/decision-packets/{packet_id}/candidate-hte.
This candidate-only DecisionPacket view requires a resource-bound RUNS_REVIEW grant for the packet
owner run, resolves packet/profile selectors from that run's indexed outputs, and reads the exact
profile through the bounded Core JSON reader. The persisted HTE summary and full owner association
must match a fresh completed-method HTE owner projection, with only aware ordered verified_at time
allowed to advance. The route currently accepts only same-owning-run source identities; cross-run
packet selectors return cross_run_authorization_not_established until a separate source-run
authorization owner exists. Publication authorization and live source currentness remain
not_established. Generic artifact content remains blocked by its closeout-authority gate.

The runs router exposes POST and GET predictive-calibration operations under exact owned-run bindings. POST reuses the existing RUNS_FEEDBACK_EVALUATE permission for an owner-bound candidate diagnostic write; GET uses RUNS_REVIEW for the same run ownership. Both permission/resource pairs are explicit Rego contracts and default deny remains in force. POST appends an immutable association ref only after the ForecastOwner, empirical bridge, and S10 paths complete. GET verifies the event payload hash, reopens the association and evidence, and recomputes S10. Neither endpoint promotes prediction evidence into causal credibility.

## Generic N5 candidate and joint-parent readback

`GET /api/v1/runs/{run_id}` can expose the typed `generic_cycle_simulation` projection from the
persisted recursive run. Version v5 separates `n5_observations` for individual child cycles from
`joint_parent_observations` for the parent's joint candidate assessment. A resolved parent row
carries the selected N5 result reference, checked-model interaction evidence, and the candidate
selection's source relationship. When the N8 consumer can read the parent result, its
`value_conditional` observation has decision grade `low`; missing coupling scope, hypothetical
composition and child-to-parent refinement remain explicit limitations. An unavailable or invalid selected parent-result view leaves its parent status
`not_established` with a typed limitation, while independently replayed child rows remain available.
A known selected-view tenant/cell mismatch or a typed ownership denial refuses the GET without
returning child data; an ordinary backing-filesystem permission failure produces a dependency
refusal rather than an inferred tenant denial. A selected-view verifier reopens the original owner,
raw/typed manifest and body bytes instead of interpreting `has` or `verify=False` as permission
proof. This bounded behavior covers selected N5 parent/child replay; other earlier source failures
can still prevent the projection. If a store cannot reopen the derived exact view of a profileless
historical generic compiled root, the generic projection can remain not established. The same
limitation on a profileless generic result can remove that candidate row; retaining either case as a
declared limited generic candidate on a default-only store remains unverified. These observations do not
establish an authored compound policy, world evidence, currentness or publication authority.

For a generic child, the selected execution owner reconciles the selected input, request and
result with the source, profile, problem, candidate and run scope. `n5_owner_join_status`
distinguishes `resolved`, `unavailable`, `invalid`, `mismatch` and `not_established`. An
independently readable result can remain a candidate with a provenance limitation when the owner
view is unavailable; an established invalid or mismatched join blocks that row. Other independently
replayed child rows remain in the projection for those child-owner outcomes. A selected artifact reference locates bytes for a separately
authorized reader; a request/result consistency check or content-bound receipt does not
independently authenticate the numerical producer.

A non-generic profileless compiled reference with an accessible, valid declared canonical manifest
is read through its actual owner, with its raw/typed manifest, body digest and selected-profile
projection reconciled. A missing or malformed canonical declaration is not admitted by this path. The original owner handle is
then retained for acquisition-history joins. Such an unqualified root carries
`compiled_cycle_selected_view_not_established` on retained N5 and N8 candidates; a `value_ready`
observation is surfaced as pending. The default-only owner and resolved acquisition-history
witnesses are authored but have not run on the composed tree.

Historical generic v1–v4 payloads remain readable by the updated dashboard validator. An older
strict client that only accepts v1–v4 cannot consume a v5 response; regenerate the OpenAPI and
runtime client/dashboard types and verify installed consumers before rollout. Historical
non-generic candidate-simulation execution records V2–V5 do not provide a complete selected request
join. Their K_sim results can remain usable as limited candidates, while the older unmarked
EvalSafety input path and authority-grade physical-run/producer provenance require separate owner
verification. ProgramGraph request references that are excluded from serialized request bytes also
require an actual selected-owner rehydration path; no missing reference or producer attestation is
inferred here. The synthetic fresh POST, worker, selected-result, GET and N8 tests and dashboard
semantic tests are authored; runtime and removal evidence must be obtained on the composed tree.

## Acquisition history v3

Fresh run GET dispatches terminal manifests by version before parsing the
legacy terminal. Route `@2.0` uses
`acquisition_evaluation_history.verify_acquisition_retention_history`, which
reopens the selected source, growth, decision, frontier and verified route fold.
Only its retained projection enters the v3 DTO. Foreign, unknown, incomplete or
mismatched closure returns typed incomplete history; readable blobs or payload
flags do not grant a successful join. Legacy-shaped verified v2 terminals use
the existing no-growth/reentry renderer. Retained rows keep all new-evaluation
fields null and preserve original evaluation inputs and occurrence identity.
Currentness remains `not_established`, authority remains
`candidate_observation_only`, and publication authority remains false.
