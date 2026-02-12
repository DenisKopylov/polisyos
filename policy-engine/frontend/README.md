# `frontend/` — API-first интерфейсы Runtime API v1

Директория `frontend` содержит минимальный frontend foundation для наблюдаемости runtime:
- сгенерированный HTTP-клиент по OpenAPI-контракту;
- reference shell для отладки run/timeline/node/artifact через Runtime API.
- новый React/Vite dashboard scaffold для Phase 0.

Это не продуктовый UI, а опорный слой для стабильного API-driven сценария.

## Роль в системе

`frontend` закрывает разрыв между backend-контрактами и UI-диагностикой:
- фиксирует машинно-генерируемый контракт клиента (`runtime-api-client`);
- дает рабочий shell без прямых чтений CAS/файлов/БД (`runtime-reference-shell`);
- дает Typed React-приложение для Phase 0/1/2 (`runtime-dashboard`);
- поддерживает cutover на Runtime API v1 как единственную online-точку доступа к runtime-данным.

## Состав директории

| Директория | Назначение |
| --- | --- |
| `frontend/runtime-api-client/` | Typed клиент (`.ts`) и runtime ESM-клиент (`.js`), генерируются из OpenAPI |
| `frontend/runtime-reference-shell/` | Статический reference UI (HTML/CSS/JS), использует только `RuntimeApiClient` |
| `frontend/runtime-dashboard/` | React 18 + TypeScript + Vite scaffold с React Query и typed API hooks |

## Архитектура и поток контрактов

```text
src/polisyos/runtime/http/* (FastAPI Runtime API v1, read-only)
  -> tools/runtime/export_runtime_openapi.py
  -> schemas/runtime_api_v1.openapi.json
  -> tools/runtime/generate_runtime_client.py
  -> frontend/runtime-api-client/runtimeApiClient.ts + runtimeApiClient.js
  -> frontend/runtime-reference-shell/app.js
  -> frontend/runtime-dashboard/src/api/types.ts (openapi-typescript)
```

## Инварианты и границы

- UI-поток строго API-only: frontend не читает `.polisyos/runs`, CAS или DuckDB напрямую.
- Runtime API слой для этого frontend-а read-only (`GET` endpoints).
- Текущий канонический `source_kind` для runtime API: `core_run`.
- `runtime-reference-shell` не использует npm/build toolchain (статические файлы).
- `runtime-dashboard` использует npm toolchain (`Vite + TypeScript + Tailwind`).

## Связь с другими директориями

- `src/polisyos/runtime/` — backend Runtime API v1.
- `src/polisyos/core/contracts/runtime.py` — DTO/контракты ответов API.
- `schemas/runtime_api_v1.openapi.json` — источник для генерации frontend-клиента.
- `tools/runtime/export_runtime_openapi.py` — экспорт OpenAPI.
- `tools/runtime/generate_runtime_client.py` — генерация `runtimeApiClient.ts/js`.
- `frontend/runtime-dashboard/scripts/generate-api-client.sh` — генерация `src/api/types.ts`.
- `tests/runtime/http/test_runtime_api_no_legacy_sources.py` — инварианты core-only source kinds.

## Локальный запуск reference shell

Из корня `policy-engine/`:

```bash
PYTHONPATH=src uv run --extra multi-tenant --extra test python - <<'PY'
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn

app = create_runtime_api_app()
uvicorn.run(app, host="127.0.0.1", port=8000)
PY

cd frontend/runtime-reference-shell
python -m http.server 4173
```

Далее открыть `http://127.0.0.1:4173` и указать base URL API.

## Локальный запуск runtime dashboard (Phase 0)

Из корня `policy-engine/`:

```bash
cd frontend/runtime-dashboard
npm install
npm run generate:api
npm run dev
```

Открыть `http://127.0.0.1:5173`.
