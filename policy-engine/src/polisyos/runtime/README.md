# Runtime (`polisyos.runtime`)

## Purpose

`polisyos.runtime` is the runtime-facing boundary for replay planning,
completeness checks, verification, and the committed runtime API package under
`polisyos.runtime.http`. It bridges CAS-backed run state to HTTP, generated
clients, dashboards, and operator tooling.

## Where to Start

- `src/polisyos/runtime/__init__.py` for the stable replay facade.
- `src/polisyos/runtime/replay.py` for replay planning and verification logic.
- `src/polisyos/runtime/http/README.md` for the FastAPI app, route layout, and
  service layer.

- `docs/reference/api/index.md` for the committed runtime API surface.
- `tools/ops_runners/runtime/check_runtime_api_contract.py` for OpenAPI drift checks.

## Public API

- Supported package entrypoint: `polisyos.runtime`
- Lazy exports from `src/polisyos/runtime/__init__.py`: `ReplayStrategy`,
  `ReplayPlan`, `CompletenessLevel`, `CompletenessReport`, `VerificationMode`,
  `VerificationConfig`, `VerificationResult`, `build_replay_plan`,
  `completeness_check`, `verify_replay`

- `polisyos.runtime.http` owns the runtime API assembly and OpenAPI snapshot
  inputs. Use its README when working on HTTP wiring, security middleware, or
  generated-client drift.

## Internal Layout

- `__init__.py` and `replay.py` own the root replay facade.
- [`http/`](http/README.md) owns the FastAPI app, route/service layout,
  OpenAPI inputs, middleware, and generated-client compatibility surface.
- [`extensions/`](extensions/) owns runtime extension ABI helpers.
- Runtime-state migrations and retention policy live under
  [`../../../ops/migrations/runtime_state/README.md`](../../../ops/migrations/runtime_state/README.md)
  and [`../../../architecture/local_runtime_state.toml`](../../../architecture/local_runtime_state.toml).

## Extension Points

Runtime middleware plugins use the `polisyos.runtime_middlewares` entry-point
group declared in
[architecture/extension_points.toml](../../../architecture/extension_points.toml).
HTTP service behavior should be exposed through routes and OpenAPI contracts,
not by deep-importing service internals.

## Depends on / depended on by

Depends on: `polisyos.common`, `polisyos.core.contracts`,
`polisyos.core.artifacts`, `polisyos.core.security`, and the
`polisyos.runtime.http` subpackage for API assembly.

Depended on by: `packages/runtime-api-client`,
`apps/runtime-dashboard`, `apps/runtime-reference-shell`, runtime
runbooks, contract checks, and control-plane tooling.

## Common commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "import polisyos.runtime as runtime; print(sorted(runtime.__all__))"`

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python -c "import polisyos.runtime.http as runtime_http; print(sorted(runtime_http.__all__))"`

- Conceptual regeneration:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`

- Conceptual regeneration:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts packages/runtime-api-client/runtimeApiClient.ts --out-js packages/runtime-api-client/runtimeApiClient.js`

## Tests

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/test_replay_runtime.py tests/unit/runtime/test_replay_input_bindings_completeness.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_api_maturity.py`

## Operability Links

- [Runtime component SLO](../../../ops/components/runtime/slo.yaml)
- [Runtime component runbooks](../../../ops/components/runtime/runbooks.md)
- [Runtime API outage runbook](../../../docs/runbooks/runtime-api-outage.md)
- [Runtime graceful shutdown and stuck worker runbook](../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md)
- [Deploy runtime how-to](../../../docs/how-to/deploy-runtime.md)

## Known Shims/Deprecations

There are no active package-local root shims for `polisyos.runtime` in
[architecture/shims.toml](../../../architecture/shims.toml) as of 2026-05-06.
`runtime/http/services/control.py` and `runtime/http/openapi_contract.py` are
tracked in [architecture/module_size_budget.toml](../../../architecture/module_size_budget.toml)
with owner `team-runtime` and sunset `2026-12-31`.

## Reference docs

- [Runtime HTTP](http/README.md)
- [REST API Reference](../../../docs/reference/api/index.md)
- [Runs API](../../../docs/reference/api/runs.md)
- [Control Plane API](../../../docs/reference/api/control.md)
- [Artifact Inspection API](../../../docs/reference/api/artifacts.md)
- [Generated Artifacts](../../../docs/reference/generated-artifacts.md)
- [Runtime API client](../../../packages/runtime-api-client/README.md)
- [Runtime dashboard](../../../apps/runtime-dashboard/README.md)
- [Runtime reference shell](../../../apps/runtime-reference-shell/README.md)

- Last updated: 2026-05-06
