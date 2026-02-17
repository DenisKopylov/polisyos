# Runtime HTTP API (`polisyos.runtime.http`)

`polisyos.runtime.http` — FastAPI слой runtime API v1: health/read/debug/artifact endpoints и control-plane операции.

Документ отражает текущее состояние кода на **2026-02-17**.

## Роль и границы

- Предоставляет HTTP-контур для introspection/debug над `core_run` и CAS артефактами.
- Выполняет control-plane операции (launch run, ingestion/retrieval, Lex pipeline actions).
- Не хранит бизнес-данные самостоятельно: использует `FileSystemCAS`, `core_runs_root` и сервисы из `scientist/fabric/lex`.

## Архитектура директории

```text
http/
├── app.py                  # create_runtime_api_app + middleware wiring + OpenAPI install
├── dependencies.py         # RuntimeApiContext + authz/tenant helpers
├── errors.py               # application/problem+json модель ошибок
├── openapi_contract.py     # operation examples + unified problem responses
├── jwt_auth_middleware.py  # JWT auth, AccessScope binding
├── cell_router_middleware.py
├── authz_middleware.py
├── routes/                 # HTTP endpoints
└── services/               # domain services (run index, debug, lineage, control, ...)
```

## Request pipeline

```text
HTTP request
  -> app.py (FastAPI app + exception handlers)
  -> telemetry middleware (request_id, metrics/tracing)
  -> optional security chain (JWT -> CellRouter -> Authz)
  -> routes/*
  -> services/*
  -> FileSystemCAS + core_runs_root
```

Важно: security middlewares выключены по умолчанию и подключаются только при `enable_security_middlewares=True`.

## Актуальные endpoint'ы

### Health

- `GET /health`
- `GET /ready`
- `GET /api/v1/health`

### Runs (`/api/v1/runs`)

- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/timeline`
- `GET /api/v1/runs/{run_id}/nodes`
- `GET /api/v1/runs/{run_id}/lineage`
- `GET /api/v1/runs/{run_id}/agents`
- `GET /api/v1/runs/{run_id}/workflow`

### Debug (`/api/v1/debug/runs`)

- `GET /api/v1/debug/runs/{run_id}/nodes/{alias}`
- `GET /api/v1/debug/runs/{run_id}/governance`
- `GET /api/v1/debug/runs/{run_id}/errors`

### Artifacts (`/api/v1/artifacts`)

- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/lineage`
- `GET /api/v1/artifacts/{artifact_id}/schema`

### Control-plane (`/api/v1/control`)

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
- `GET /api/v1/control/data/profiles`
- `GET /api/v1/control/data/binding-profiles`
- `GET /api/v1/control/llm/profiles`
- `POST /api/v1/control/lex/trigger`
- `GET /api/v1/control/lex/status/{pipeline_id}`
- `GET /api/v1/control/lex/graph/stats`
- `POST /api/v1/control/lex/search`

## Security и tenant isolation

- JWT auth middleware валидирует Bearer токен, строит `AccessScope`, сверяет tenant header/token.
- Cell router middleware резолвит tenant->cell routing и защищает от cross-tenant/cell mismatch.
- Authz middleware формирует `AuthzInput` и запрашивает OPA; поддерживает enforce/shadow режимы.
- Маршруты передают ресурсный контекст через `set_authz_resource(...)`.
- Доступ к run/artifact дополнительно ограничивается tenant-check helper'ами:
  - `enforce_run_tenant_access`
  - `enforce_artifact_tenant_access`

## Observability и error model

- `X-Request-ID` создается/прокидывается на каждый запрос.
- Request telemetry пишет tracing span и runtime API latency/status метрики.
- Все ошибки нормализуются в `application/problem+json` (`RuntimeApiProblem`).
- `openapi_contract.py` дополняет OpenAPI примерами success/error payload для операций.

## Ключевые настройки

Параметры `create_runtime_api_app(...)`:

- Хранилища и лимиты: `cas_root`, `core_runs_root`, `max_preview_bytes`, `lineage_max_depth`, `lineage_max_nodes`.
- Поведение tenant enforcement: `allow_unscoped_artifacts`.
- API runtime behavior: `enable_response_compression`, `artifact_redaction_hooks`.
- Security wiring: `enable_security_middlewares`, `identity_provider`, `cell_registry`, `opa_client`, `authz_enforce`, `authz_shadow_mode`, delegation settings.

Ключевые ENV-флаги, используемые внутри HTTP слоя:

- `POLISYOS_CELL_ID`
- `POLISYOS_SERVICE_SPIFFE_ID`
- `POLISYOS_LLM_MULTIMODEL_ENABLED`
- `POLISYOS_REQUIRED_PREFLIGHT_ENABLED`
- `POLISYOS_AUTO_MATERIALIZATION_ENABLED`
- `POLISYOS_UNIFIED_DAG_ENABLED`

## Связанные подсистемы

- `polisyos/runtime/http/services/*` — прикладная логика route handlers.
- `polisyos/core/contracts/runtime.py` и `polisyos/core/contracts/control.py` — API контракты.
- `polisyos/runtime/http/services/control.py` — bridge к `scientist`, `fabric`, `lex`.

## Поддиректории с отдельной документацией

- [services/README.md](services/README.md)
