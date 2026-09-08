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

- `src/polisyos/runtime/http/permissions.py` for the server-owned action
  permission vocabulary and immutable role grants projected by `/auth/me`.

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
  `mutation_policy.py`, `openapi_contract.py`, `permissions.py`

## Authorization contract

`RuntimePermission` is the only hand-authored permission vocabulary for the
runtime API. Role grants consume enum members, and DS20's route-admission
dependency will consume the same members. The HTTP-local `AuthMeResponse`
projects the enum into OpenAPI for generated clients. Unknown string literals
do not become permissions by appearing in a client.

`GET /api/v1/auth/me` returns only claims installed by verified identity
middleware. It never synthesizes a fixture identity; the explicit development
fixture middleware may still install development-only claims before the route
executes.

The runtime container appoints one Decision Validity service for control and promotion. Read-only
run-index/debug adapters may open their own service view, but every view resolves the same locked
persistent owner state. Direct, recursive, HTTP, and offline promotion paths resolve the same
persisted epoch-validity subject and gate evidence; a route-local state or caller-shaped projection
cannot bypass that owner.

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

2026-07-18

## Source-bound value selection

The default `natural_language_run` worker persists an additive normative composition
sidecar after the compiled generation run. Each leaf preserves the actual candidate
fronts with `dominance_status=not_established`; an absent or unauthorized schedule
produces zero recommendations and a persisted `NormativeDecisionRequest`.
`get_job_status` and `get_latest_job_for_run` share current replay: compiled membership,
leaf source bytes, signatures, deployment scope and expiry are checked at each read.
A missing or invalid sidecar produces a fresh refusal from the available compiled
source. An unresolved source is reported explicitly as `not_established`.

Deployment code may pass a typed `NormativeAuthorityTrust` through
`create_runtime_api_app(normative_authority_trust=...)`; the default slot is empty.
Request context accepts only `normative_evidence.by_node` references to a genuine S8
frontier and a signed `policyos.normative_authorization.v2` record binding the exact
compiled source, leaf source and node. This permission authorizes the recorded
selection; it confers no empirical, Pareto, legal or publication authority. The
canonical ambient filesystem CAS is reused with its ownership checks. Other CAS
backends require an independently verified signed-store adapter.

The sidecar contracts are internal Python owner surfaces; the existing HTTP
`ControlJobResponse.progress` carries their additive projection and CAS references.
Existing generation DTOs and standalone S8 authorization v1 artifacts retain their
epochs. Targeted replay and removal controls live in
`tests/unit/runtime/http/test_normative_generation_bridge.py`.

After the worker completes, `POST /api/v1/control/runs/{run_id}/normative-evidence`
accepts the exact `job_id`, required nullable `expected_prior_head_ref`, and typed
`evidence.by_node` references. The existing owned-run resolver and `evidence.resolve`
permission govern this intake. The worker publishes its candidate computation
through the canonical core `RunContext`, preserving tenant/cell ownership; a core
`ok` execution manifest does not confer policy promotion authority.

Successful admission appends an immutable `policyos.normative_generation_head.v1`
CAS record and a `normative_evidence_admitted` job event. The store compares the exact
prior head inside a SQLite write transaction or a PostgreSQL owning-job row lock.
A signed but invalid input persists a refusal and returns HTTP 422; a stale expected
head returns HTTP 409. Neither replaces the admitted head. The response carries the
attempted disposition, current head and current job projection. Both job readers
bind the head to the exact job, run and immutable compiled output, then replay S8
source/signature/scope/time checks. General progress updates cannot rewrite this
append-only head. Requests accept no source, deployment-trust or signature overrides.

The immutable core-run outputs own both the initial default and later head lookup.
A copied `progress` projection cannot supply a current head or change its source.
A missing event or mismatched progress reference produces a fresh refusal using the
known canonical source, preserving its candidate fronts and typed request. If that
owned source itself cannot be resolved, current authority is `blocked` with an
explicit source limitation; standalone historical sidecar replay remains available.
