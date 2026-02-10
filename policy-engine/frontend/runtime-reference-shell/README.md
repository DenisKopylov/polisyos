# Runtime Reference Shell

Reference frontend shell for Runtime API v1 foundation.

## Scope

- Run list page (`/api/v1/runs`)
- Run timeline + node graph page (`/api/v1/runs/{run_id}/timeline`, `/nodes`)
- Node debug panel (`/api/v1/debug/runs/{run_id}/nodes/{alias}`)
- Artifact inspector panel (`/api/v1/artifacts/*`)

The shell is API-only and never reads DuckDB or runtime files directly.

## Run locally

1. Start runtime API service (example):

```bash
uv run --extra multi-tenant --extra test python - <<'PY'
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn

app = create_runtime_api_app()
uvicorn.run(app, host="127.0.0.1", port=8000)
PY
```

2. Serve frontend files:

```bash
cd frontend/runtime-reference-shell
python -m http.server 4173
```

3. Open `http://127.0.0.1:4173` and set base URL to your runtime API host.
