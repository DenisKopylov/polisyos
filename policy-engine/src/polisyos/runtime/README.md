# `polisyos.runtime`

Runtime subsystem that provides:

- Runtime HTTP API v1 for read-only run/artifact introspection.
- Replay planning and verification APIs for deterministic re-execution checks.
- Compatibility helpers for legacy filesystem run manifests.

## Current Scope (P10+)

- Runtime API v1 serves only `core_run` sources.
- Runtime API v1 does not ingest legacy `runs/*/manifest.json` shape.
- Public `polisyos.runtime` package exports replay API (`replay.py`) via lazy imports.
- HTTP layer is read-only (`GET` endpoints only).

## Architecture At A Glance

```text
HTTP request
  -> runtime/http/app.py (FastAPI app + exception handlers)
  -> request telemetry middleware (request_id, metrics/tracing)
  -> optional security chain:
       JWTAuthMiddleware -> CellRouterMiddleware -> AuthzMiddleware
  -> routes/* (runs, debug, artifacts, health)
  -> services/* (index, timeline, debug, lineage, inspector)
  -> FileSystemCAS + core runs directory (.polisyos/runs)
```

Data sources:

- CAS manifests/payloads from `FileSystemCAS` (`cas_root`, default `.polisyos`).
- Core run directories (`core_runs_root`, default `.polisyos/runs`) with `trace.jsonl`.
- Core run manifest references discovered from `RUN_FINALIZED` trace events.

## Directory Map

```text
runtime/
├── __init__.py      # Public lazy exports for replay API only
├── replay.py        # Replay strategy, completeness checks, verification
├── api.py           # Legacy filesystem run helpers (start/log/finalize)
├── manifest.py      # Legacy RunManifest/ArtifactRef models
└── http/            # Runtime API v1 (FastAPI app, routes, services, middleware)
    ├── app.py
    ├── dependencies.py
    ├── errors.py
    ├── routes/
    └── services/
```

## Runtime HTTP API v1

Base endpoints:

- `GET /health`
- `GET /ready`
- `GET /api/v1/health`

Runs:

- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/timeline`
- `GET /api/v1/runs/{run_id}/nodes`
- `GET /api/v1/runs/{run_id}/lineage`

Debug:

- `GET /api/v1/debug/runs/{run_id}/nodes/{alias}`
- `GET /api/v1/debug/runs/{run_id}/governance`
- `GET /api/v1/debug/runs/{run_id}/errors`

Artifacts:

- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/lineage`
- `GET /api/v1/artifacts/{artifact_id}/schema`

Notes:

- `source_kind` is canonical and currently always `core_run`.
- OpenAPI schema uses `core.contracts.runtime` DTOs and excludes legacy source kinds.
- Error responses are unified as `application/problem+json` (`RuntimeApiProblem` schema).
- Every Runtime API operation includes OpenAPI response examples (success + problem payloads).

## Services And Module Responsibilities

`http/services/run_index.py`:

- Builds in-memory index of core runs from `core_runs_root`.
- Uses `services/adapters/core_run.py` to normalize run metadata.
- Caches index with short TTL (default 2s) for repeated API calls.
- Maintains artifact -> tenant mapping for artifact-level tenant enforcement.

`http/services/timeline.py`:

- Parses `trace.jsonl` into ordered timeline events.
- Produces run summary metrics (duration, phase counts, cache hit/store/bypass).

`http/services/debug.py`:

- Provides node-level, governance, and aggregated error debug views.
- Merges workflow-report node metadata with trace-derived context.
- Redacts sensitive payload fields (`token`, `password`, `authorization`, etc.).
- Governance debug prefers governance report from experiment state, with decision-packet fallback.

`http/services/lineage.py`:

- Resolves dependency graphs from CAS artifacts (`resolve_dependency_graph`).
- Returns merged lineage view with missing/corrupted artifacts and completeness flags.

`http/services/artifact_inspector.py`:

- Manifest view from CAS metadata.
- Content preview modes: `json`, `text`, `binary`.
- Preview limit defaults to 64 KiB (`max_bytes` clamped to `1024..2_000_000`).
- Redacts sensitive artifact kinds and supports custom redaction hooks.

## Security And Tenant Isolation

Security middlewares are disabled by default. To enable, provide:

- `identity_provider` (JWT claims extraction),
- `cell_registry` (tenant -> cell routing),
- `opa_client` (authorization decision).

When enabled:

- JWT middleware binds authenticated tenant/cell scope.
- Cell router enforces tenant header/token consistency and tenant-cell routing.
- Authz middleware checks request/resource context in OPA and can run in enforce or shadow mode.
- Route handlers add resource context (`set_authz_resource`) and apply tenant checks:
  - run access: `enforce_run_tenant_access`
  - artifact access: `enforce_artifact_tenant_access`
- Unscoped artifacts are denied unless `allow_unscoped_artifacts=True`.

## Replay API (`replay.py`)

Core entry points:

- `build_replay_plan`
- `completeness_check`
- `verify_replay`

Capabilities:

- Strategy detection (`foundry`, `scientist`, `none`) from packet references.
- Required-role validation (e.g. `input_bindings_ref`, snapshot refs).
- Completeness classification (`complete`, `recoverable`, `incomplete`).
- Seed resolution from replay block, run record, payload, or exec plan.
- Verification modes:
  - `bit_exact` (artifact id equality),
  - `ci_bounded` (metric drift tolerance),
  - `skip`.

Used by:

- `polisyos/scientist/replay_backend.py`
- `polisyos/core/components/_cli_replay.py`

## Legacy Filesystem Runtime Helpers (`api.py`, `manifest.py`)

These modules are retained for compatibility and tests:

- Create/update `runs/<run_id>/manifest.json`.
- Log artifacts to filesystem and store relative paths for relocatability.
- Resolve artifact paths from relative/absolute refs.

They are not part of Runtime API v1 serving path and are not exported from
`polisyos.runtime.__all__`.

## Integration With Other Directories

- `polisyos/core/contracts/runtime.py`: HTTP response/request DTOs.
- `polisyos/core/artifacts/*`: IDs, manifests, store, graph traversal, canonical decoding.
- `polisyos/core/security/*`: JWT identity, cell routing, access scope, OPA authz.
- `polisyos/core/trace/record.py`: trace schema for timeline/debug extraction.
- `tools/runtime/*`: OpenAPI export, client generation, legacy run archive/inventory tools.

## Local Run

```bash
PYTHONPATH=src uv run --extra multi-tenant --extra test python - <<'PY'
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn

app = create_runtime_api_app()
uvicorn.run(app, host="127.0.0.1", port=8000)
PY
```

## Runtime Tooling

Export OpenAPI:

```bash
PYTHONPATH=src uv run python tools/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json
```

Generate typed client from schema:

```bash
PYTHONPATH=src uv run python tools/runtime/generate_runtime_client.py \
  --openapi schemas/runtime_api_v1.openapi.json
```

Validate OpenAPI drift and contract invariants:

```bash
PYTHONPATH=src uv run python tools/runtime/check_runtime_api_contract.py
```
