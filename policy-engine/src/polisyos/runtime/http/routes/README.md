# Runtime HTTP Routes (`polisyos.runtime.http.routes`)

`routes/` — тонкий HTTP-слой runtime API v1. Здесь только request/response wiring, authz context и вызовы сервисов из `../services`.

Документ отражает текущее состояние кода на **2026-03-03**.

## Структура

```text
routes/
├── health.py     # liveness/readiness/runtime health
├── runs.py       # run list/details/timeline/nodes/lineage/agents/workflow
├── debug.py      # node/governance/errors debug
├── artifacts.py  # manifest/content/lineage/schema по artifact_id
└── control.py    # запуск run + data/lex control-plane API
```

## Карта endpoint'ов

### `health.py`

- `GET /health`
- `GET /ready`
- `GET /api/v1/health`

### `runs.py` (`/api/v1/runs`)

- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/timeline`
- `GET /api/v1/runs/{run_id}/nodes`
- `GET /api/v1/runs/{run_id}/lineage`
- `GET /api/v1/runs/{run_id}/agents`
- `GET /api/v1/runs/{run_id}/workflow`

### `debug.py` (`/api/v1/debug/runs`)

- `GET /api/v1/debug/runs/{run_id}/nodes/{alias}`
- `GET /api/v1/debug/runs/{run_id}/governance`
- `GET /api/v1/debug/runs/{run_id}/errors`

### `artifacts.py` (`/api/v1/artifacts`)

- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/lineage`
- `GET /api/v1/artifacts/{artifact_id}/schema`

### `control.py` (`/api/v1/control`)

- `POST /api/v1/control/runs`
- `POST /api/v1/control/runs/nl`
- `POST /api/v1/control/data/ingest`
- `POST /api/v1/control/data/resolve`
- `POST /api/v1/control/data/discover`
- `POST /api/v1/control/data/preview`
- `GET /api/v1/control/data/catalog/search`
- `GET /api/v1/control/data/index/stats`
- `GET /api/v1/control/data/promotion/candidates`
- `POST /api/v1/control/data/promotion/{promotion_id}/approve`
- `POST /api/v1/control/data/promotion/{promotion_id}/reject`
- `GET /api/v1/control/data/connectors`
- `GET /api/v1/control/data/cache`
- `GET /api/v1/control/llm/profiles`
- `GET /api/v1/control/data/profiles`
- `GET /api/v1/control/data/binding-profiles`
- `POST /api/v1/control/lex/trigger`
- `GET /api/v1/control/lex/status/{pipeline_id}`
- `GET /api/v1/control/lex/graph/stats`
- `POST /api/v1/control/lex/search`

## Cross-cutting поведение в routes

- Каждый handler возвращает DTO из `polisyos.core.contracts.runtime/control`.
- `build_meta(...)` добавляет `request_id` и source kinds в `meta`.
- `set_authz_resource(...)` выставляет ресурсный контекст для `AuthzMiddleware`.
- `runs.py` и `debug.py` вызывают `enforce_run_tenant_access(...)`.
- `artifacts.py` вызывает `enforce_artifact_tenant_access(...)`.
- `control.py` lazily создаёт `ControlPlaneService` и кэширует его в `request.app.state._control_service`.

## Что важно при расширении routes

- Новые request/response модели добавлять в `polisyos.core.contracts.*`, не локально в route-модуле.
- Для доступа к данным run/artifact всегда задавать `set_authz_resource(...)` и tenant checks.
- После добавления endpoint обновлять OpenAPI enrichment в `../openapi_contract.py`.
