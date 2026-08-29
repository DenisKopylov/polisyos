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
- **Governed projection routes** - retain the generic 13-ID read surface and add
  one static-before-dynamic confidence-ledger risk-spend GET. That specialized
  operation is reviewer-protected with tenant-collection binding and is its
  guarded source's sole HTTP surface.
- **Epoch-validity batch intake** - accepts only a transition artifact ref and requested query
  context. Status, targets, dependency keys, dedupe values, and verifier identity are resolved by
  the container-owned Decision Validity service rather than accepted from HTTP callers.

## Public API

- route modules: `health.py`, `runs.py`, `debug.py`, `artifacts.py`, `control.py`,
  `human_decisions.py`, `governed_projections.py`
- route routers exported from `__init__.py`: `health_router`, `runs_router`,
  `debug_router`, `artifacts_router`, `control_router`, `human_decisions_router`

## Current State

- Last updated: 2026-08-29
- The control-plane surface still includes the broader data/lex endpoints documented in the current routes.
- `openapi_contract.py` now mirrors new control and decision-validity examples that sit behind these routes.
- Completed human-decision exposure receipts are appended only by the dedicated
  exact-byte response path in the existing access-audit trail; generic artifact
  reads and generic audit appends cannot mint them.
