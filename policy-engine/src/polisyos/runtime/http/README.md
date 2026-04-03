# Runtime HTTP (`polisyos.runtime.http`)

`polisyos.runtime.http` is the FastAPI layer for the runtime API v1. It hosts health, runs, debug,
artifact, and control-plane endpoints plus the middleware and OpenAPI enrichment used by the app.

## Role in System

- **Depends on:** `core.contracts`, `core.security`, `core.artifacts`, and the service layer under `runtime.http.services`.
- **Used by:** runtime API clients, operator tooling, and the control-plane entrypoints.
- **Boundary function:** keeps HTTP request wiring thin while the service layer owns the application logic.

## Key Concepts

- **App factory** - `app.py` builds the FastAPI app and wires middleware and routes.
- **Middleware chain** - JWT, cell routing, and authz middleware protect tenant-scoped requests.
- **Routes** - `routes/` contains thin request handlers only.
- **Services** - `services/` contains run index, debug, lineage, artifact, and control-plane logic.
- **OpenAPI enrichment** - `openapi_contract.py` keeps examples and problem responses aligned with the current API.

## Public API

- `create_runtime_api_app`
- `export_runtime_openapi_schema`
- `AuthzMiddleware`
- `CellRouterMiddleware`
- `JWTAuthMiddleware`
- `TENANT_HEADER`
- `get_current_user`

## Current State

- Last updated: 2026-04-03
- `openapi_contract.py` now includes example payloads for control workers, outbox events, and decision-validity responses.
- Security middleware remains opt-in through `create_runtime_api_app(..., enable_security_middlewares=True)`.
