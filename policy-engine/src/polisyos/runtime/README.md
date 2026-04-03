# Runtime (`polisyos.runtime`)

`polisyos.runtime` provides the runtime-facing surface of PolicyOS: replay planning and verification,
legacy filesystem helpers, and the HTTP API package under `runtime.http`.

## Role in System

- **Depends on:** `core.contracts`, `core.artifacts`, and the HTTP/service subpackages for runtime inspection.
- **Used by:** runtime API clients, replay tooling, and control-plane orchestration.
- **Boundary function:** bridges CAS-backed run state with the higher-level HTTP and replay surfaces.

## Key Concepts

- **Replay API** - `replay.py` exposes planning, completeness, and verification helpers.
- **Legacy helpers** - `api.py` and `manifest.py` keep old filesystem-based run handling working.
- **HTTP surface** - `runtime.http` hosts the FastAPI app, routes, middleware, and service layer.

## Public API

- `ReplayStrategy`
- `ReplayPlan`
- `CompletenessLevel`
- `CompletenessReport`
- `VerificationMode`
- `VerificationConfig`
- `VerificationResult`
- `build_replay_plan`
- `completeness_check`
- `verify_replay`

## Current State

- Last updated: 2026-04-03
- The top-level package still exports only the replay facade; HTTP helpers live under `runtime.http`.
- The HTTP OpenAPI contract now carries additional control examples for workers, outbox, and decision-validity surfaces.
