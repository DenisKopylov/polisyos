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

