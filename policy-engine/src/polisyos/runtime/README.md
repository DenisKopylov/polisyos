# Runtime (`polisyos.runtime`)

`polisyos.runtime` — runtime-слой PolicyOS для доступа к запускам (`runs`) и CAS-артефактам через HTTP API, а также для replay/verification сценариев.

Документ отражает текущее состояние кода на **2026-02-17**.

## Роль в системе

- Runtime HTTP API v1: read/debug/lineage API для `core_run` + control-plane endpoint'ы для запуска run и data/lex операций.
- Replay API (`replay.py`): оценка replay-полноты, выбор стратегии, seed resolution, replay verification.
- Legacy compatibility helpers (`api.py`, `manifest.py`): поддержка старого filesystem run-manifest формата.

## Текущий scope

- Runtime API v1 индексирует только `core_run` источники из `core_runs_root` (по умолчанию `.polisyos/runs`).
- `source_kind` в runtime API сейчас фактически фиксирован как `core_run`.
- Индексация run опирается на `trace.jsonl` и `RUN_FINALIZED` событие с `core.run_manifest` ссылкой.
- Публичный пакет `polisyos.runtime` (через `__init__.py`) экспортирует только replay API через lazy imports.
- Legacy filesystem API не участвует в HTTP serving path и сохранен как совместимость для тестов/старых сценариев.

## Архитектура директории

```text
runtime/
├── __init__.py      # Публичный lazy facade (replay API)
├── replay.py        # Replay strategy/completeness/verification
├── api.py           # Legacy runs/<run_id>/manifest.json helpers
├── manifest.py      # Legacy RunManifest/ArtifactRef модели
└── http/            # Runtime HTTP API v1 (см. отдельный README)
```

## Ключевые потоки

1. HTTP read/debug path
`request -> http/app.py -> telemetry/security middleware -> routes/* -> services/* -> FileSystemCAS + .polisyos/runs`

2. Control-plane path
`/api/v1/control/* -> services/control.py -> scientist/fabric/lex orchestration -> CAS + run artifacts`

3. Replay path
`decision_packet_ref -> replay.build_replay_plan/completeness_check -> verify_replay(bit_exact|ci_bounded|skip)`

4. Legacy filesystem path
`start_run/log_artifact/finalize_run -> runs/<run_id>/manifest.json`

## Связь с другими директориями

| Директория | Как связана с runtime |
|---|---|
| `polisyos/core/contracts` | Runtime/Control DTO и problem schema (`runtime`, `control`) |
| `polisyos/core/artifacts` | CAS store, manifest, lineage graph, canonical decoding |
| `polisyos/core/security` | JWT identity, tenant/cell routing, OPA authz middleware |
| `polisyos/core/trace` | `TraceRecord` для timeline/debug extraction |
| `polisyos/scientist` | запуск workflow/NL run через control-plane, replay backend integration |
| `polisyos/fabric` | ingestion/retrieval/data resolve/discover/preview операции |
| `polisyos/lex` | batch pipeline trigger/status и knowledge graph query/stats |
| `tools/runtime` | OpenAPI export/client generation/contract drift checks |

## Что важно при изменениях

- Новые API-контракты сначала фиксировать в `polisyos/core/contracts/*`, затем подключать в `runtime/http`.
- Если добавляется новый run source kind (кроме `core_run`), нужно обновлять `run_index`, маршруты, OpenAPI contract и tenant enforcement.
- Security middlewares opt-in: включаются только через `enable_security_middlewares=True` и явные providers.

## Локальный запуск

```bash
PYTHONPATH=src uv run --extra multi-tenant --extra test python - <<'PY'
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

## Поддиректории с отдельной документацией

- [http/README.md](http/README.md)
- [http/services/README.md](http/services/README.md)
