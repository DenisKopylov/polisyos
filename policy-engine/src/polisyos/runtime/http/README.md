# Runtime HTTP (`polisyos.runtime.http`)

## Purpose

`polisyos.runtime.http` is the FastAPI assembly layer for runtime API v1. It
owns the app factory, auth and tenant middleware chain, thin route handlers,
service composition, OpenAPI enrichment, and the write-path protections around
runtime mutations and live streams.

## Where to start

- `src/polisyos/runtime/http/__init__.py` for the exported package surface.
- `src/polisyos/runtime/http/app.py` for app assembly, middleware order, and
  lifecycle wiring.

- `src/polisyos/runtime/http/routes/README.md` for endpoint-by-endpoint local
  navigation.

- `src/polisyos/runtime/http/services/README.md` for the application logic
  behind routes.

- `src/polisyos/runtime/http/openapi_contract.py` for examples, links, and
  contract hardening hooks.

- `src/polisyos/runtime/http/mutation_policy.py` for rate limits, idempotency,
  audit trail, and live-stream budgets.

- `src/polisyos/runtime/http/fail_closed_middleware.py` and
  `src/polisyos/runtime/http/security.py` for perimeter enforcement.

## Public entrypoints

- Package exports from `src/polisyos/runtime/http/__init__.py`:
  `create_runtime_api_app`, `export_runtime_openapi_schema`,
  `AuthzMiddleware`, `CellRouterMiddleware`, `JWTAuthMiddleware`,
  `TENANT_HEADER`, `get_current_user`

- Repo-level public-surface docs still anchor on `polisyos.runtime`; use this
  README when you need the actual HTTP assembly boundary, route/service
  navigation, or contract generation inputs.

- Internal local-navigation surfaces worth checking first: `routes/*`,
  `services/*`, `container.py`, `dependencies.py`, `execution_policy.py`,
  `mutation_policy.py`, `openapi_contract.py`

## Depends on / depended on by

Depends on: `polisyos.common.async_tools`, `polisyos.core.artifacts`,
`polisyos.core.contracts`, `polisyos.core.security`,
`polisyos.core.observability`, and local `routes/` plus `services/` packages.

Depended on by: `polisyos.runtime`, `packages/runtime-api-client`,
`apps/runtime-dashboard`, `apps/runtime-reference-shell`, operator
runbooks, and runtime contract/drift checks.

## Common commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python -c "import polisyos.runtime.http as runtime_http; print(sorted(runtime_http.__all__))"`

- Conceptual regeneration:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`

- Conceptual regeneration:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts packages/runtime-api-client/runtimeApiClient.ts --out-js packages/runtime-api-client/runtimeApiClient.js`

## Test/verification commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/http/test_runtime_api_observability.py tests/unit/runtime/http/test_api_maturity.py tests/unit/runtime/http/test_access_invariants_properties.py tests/unit/runtime/http/test_control_service_di.py tests/unit/runtime/http/test_resilience_guards.py`

## Reference docs

- [Routes](routes/README.md)
- [Services](services/README.md)
- [REST API Reference](../../../../docs/reference/api/index.md)
- [Runtime Auth and Tenant Model](../../../../docs/reference/api/auth-tenant-model.md)
- [Runtime API Versioning and Deprecation Policy](../../../../docs/reference/api/versioning.md)
- [Runtime API Migration Guide](../../../../docs/reference/api/migration-guide.md)
- [Security and Compliance](../../../../docs/reference/security-compliance.md)
- [Runtime API outage runbook](../../../../docs/runbooks/runtime-api-outage.md)
- [Runtime graceful shutdown and stuck worker runbook](../../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md)
- [Runtime API client](../../../../packages/runtime-api-client/README.md)
- [Runtime dashboard](../../../../apps/runtime-dashboard/README.md)
- [Runtime reference shell](../../../../apps/runtime-reference-shell/README.md)

## Last updated date

2026-04-17
