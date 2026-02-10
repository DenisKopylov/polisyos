# `polisyos.runtime`

Runtime package after P10 cutover:

- Runtime API v1 (`runtime/http`) serves **core CAS runs only**.
- Legacy run ingestion (`runs/*/manifest.json`) is not part of online serving.
- Public `polisyos.runtime` exports replay/verification APIs only.

## Structure

```text
runtime/
├── __init__.py      # Public replay exports only
├── http/            # Runtime API v1 (FastAPI app, routes, services, middleware)
│   ├── app.py
│   ├── routes/
│   ├── services/
│   └── *_middleware.py
└── replay.py        # Replay planning, completeness check, verification
```

## Runtime HTTP API v1

Read-only API for run explorer/debug/artifact inspection under `/api/v1`.

### Runs

- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/timeline`
- `GET /api/v1/runs/{run_id}/nodes`
- `GET /api/v1/runs/{run_id}/lineage`

`source_kind` is canonical and currently emitted as `core_run`.

### Debug

- `GET /api/v1/debug/runs/{run_id}/nodes/{alias}`
- `GET /api/v1/debug/runs/{run_id}/governance`
- `GET /api/v1/debug/runs/{run_id}/errors`

### Artifacts

- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/lineage`
- `GET /api/v1/artifacts/{artifact_id}/schema`

### Health

- `GET /health`
- `GET /ready`
- `GET /api/v1/health`

## Replay API

Replay module remains available:

- `build_replay_plan`
- `completeness_check`
- `verify_replay`

## Legacy run migration/archive tooling

Before irreversible legacy path removal, use:

- `tools/runtime/inventory_legacy_runs.py`
- `tools/runtime/archive_legacy_runs.py`

These tools are offline migration utilities and are not required for Runtime API serving.

## Local run

```bash
PYTHONPATH=src uv run --extra multi-tenant --extra test python - <<'PY'
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn

app = create_runtime_api_app()
uvicorn.run(app, host="127.0.0.1", port=8000)
PY
```
