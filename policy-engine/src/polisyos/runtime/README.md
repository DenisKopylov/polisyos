# Runtime (`polisyos.runtime`)

`polisyos.runtime` — runtime-слой PolicyOS: HTTP API v1 для `runs`/CAS, replay-планирование и verification, плюс legacy filesystem helpers для обратной совместимости.

Документ отражает текущее состояние кода на **2026-03-03**.

## Роль в системе

- Даёт HTTP-поверхность для run introspection (`runs`, `debug`, `artifacts`, `lineage`) и control-plane операций (`/api/v1/control/*`).
- Предоставляет replay API (`replay.py`): выбор стратегии replay, проверка полноты артефактов, verification (`bit_exact`, `ci_bounded`, `skip`).
- Содержит legacy API (`api.py`, `manifest.py`) для формата `runs/<run_id>/manifest.json` вне основного HTTP serving path.

## Текущий scope и ограничения

- Runtime API v1 индексирует только источник `core_run` из `core_runs_root` (по умолчанию `.polisyos/runs`).
- `source_kind` в ответах runtime сейчас фактически фиксирован как `core_run`.
- Run попадает в индекс при наличии `trace.jsonl`; если `core.run_manifest` не найден/нечитаем, run остаётся доступным, но со статусом `unknown` и warning.
- Tenant binding для artifact endpoints строится из набора run refs: root artifacts + `manifest_ref` + `trace_ref` + workflow/experiment/decision refs.
- Пакетный экспорт `polisyos.runtime` (через `__init__.py`) публикует replay API через lazy imports.

## Архитектура директории

```text
runtime/
├── __init__.py      # Публичный lazy facade (replay API)
├── replay.py        # Replay strategy/completeness/verification
├── api.py           # Legacy runs/<run_id>/manifest.json helpers
├── manifest.py      # Legacy RunManifest/ArtifactRef модели
└── http/            # Runtime HTTP API v1
    ├── app.py
    ├── routes/
    └── services/
```

## Основные потоки

1. Read/debug/artifact path  
`request -> http/app.py -> telemetry/(optional security) middleware -> routes/* -> services/* -> FileSystemCAS + core_runs_root`

2. Control-plane path  
`/api/v1/control/* -> services/control.py -> scientist/fabric/lex orchestration -> CAS + run artifacts`

3. Replay path  
`decision_packet_ref -> build_replay_plan/completeness_check -> verify_replay(...)`

4. Legacy filesystem path  
`start_run/log_artifact/finalize_run -> runs/<run_id>/manifest.json`

## Связь с другими директориями

| Директория | Как связана с runtime |
|---|---|
| `polisyos/core/contracts` | DTO и API-модели (`runtime`, `control`, `problem+json`) |
| `polisyos/core/artifacts` | CAS store, manifest IDs, dependency graph, canonical decoding |
| `polisyos/core/security` | JWT identity, tenant/cell routing, OPA authz middleware |
| `polisyos/core/trace` | `TraceRecord` для timeline/debug extraction |
| `polisyos/scientist` | workflow/NL запуск и replay-related artifacts |
| `polisyos/fabric` | ingestion и retrieval операции control-plane |
| `polisyos/lex` | batch pipeline и query/stat API для knowledge graph |
| `tools/runtime` | OpenAPI export, client generation, contract drift checks |

## Что важно при изменениях

- Сначала фиксировать новые контракты в `polisyos/core/contracts/*`, потом подключать route/service реализацию в `runtime/http`.
- Для нового `source_kind` нужно расширить минимум: `adapters/*`, `run_index`, `routes/runs.py`, `openapi_contract.py`, tenant enforcement helpers.
- Security chain opt-in: middleware включаются только при `enable_security_middlewares=True` и явной передаче providers.

## Локальный запуск

```bash
PYTHONPATH=src uv run --extra runtime-http python - <<'PY'
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn

app = create_runtime_api_app()
uvicorn.run(app, host="127.0.0.1", port=8000)
PY
```

## Runtime tooling

```bash
PYTHONPATH=src uv run python tools/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json

PYTHONPATH=src uv run python tools/runtime/generate_runtime_client.py \
  --openapi schemas/runtime_api_v1.openapi.json

PYTHONPATH=src uv run python tools/runtime/check_runtime_api_contract.py
```

## Документация поддиректорий

- [http/README.md](http/README.md)
- [http/routes/README.md](http/routes/README.md)
- [http/services/README.md](http/services/README.md)
