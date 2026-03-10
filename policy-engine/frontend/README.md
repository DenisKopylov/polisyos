# `frontend/` — Runtime API UI слой

`frontend/` содержит UI-поверхности для Runtime API v1:
- основная рабочая панель (`runtime-dashboard`);
- референсный статический shell для быстрой диагностики (`runtime-reference-shell`);
- сгенерированный JS/TS клиент (`runtime-api-client`), на котором работает reference shell.

## Роль в системе

Директория связывает backend-контракт OpenAPI с реальными UI-сценариями:
- наблюдаемость по run/artifact/debug/workflow;
- контрольные операции control-plane (запуск run, ingest/discovery/promotions, Lex pipeline);
- единый API-first подход без прямого чтения CAS/файлов/БД из frontend.

## Состав директории

| Директория | Назначение |
| --- | --- |
| `frontend/runtime-dashboard/` | React 18 + TypeScript + Vite приложение (основной UI runtime и control-plane) |
| `frontend/runtime-reference-shell/` | Статический reference UI без сборки (`index.html` + `app.js` + `styles.css`) |
| `frontend/runtime-api-client/` | Сгенерированный `RuntimeApiClient` (`runtimeApiClient.ts/js`) для JS/TS-интеграций |

## Поток контрактов и генерации

```text
src/polisyos/runtime/http/* (FastAPI Runtime API v1)
  -> tools/runtime/export_runtime_openapi.py
  -> schemas/runtime_api_v1.openapi.json
      -> tools/runtime/generate_runtime_client.py
      -> frontend/runtime-api-client/runtimeApiClient.ts + runtimeApiClient.js
      -> frontend/runtime-dashboard/scripts/generate-api-client.sh
      -> frontend/runtime-dashboard/src/api/types.ts
```

## Архитектурные границы

- Frontend работает только через HTTP API, без доступа к `.polisyos/runs`, CAS и локальным БД.
- `runtime-reference-shell` использует только сгенерированный `RuntimeApiClient`.
- `runtime-dashboard` использует `openapi-fetch` + generated types + React Query hooks; capability manifest идёт через тот же generated OpenAPI contract.
- Для runtime read-paths в dashboard применяются `zod`-валидаторы; control-plane вызовы типизированы из OpenAPI.

## Связь с другими директориями

- `src/polisyos/runtime/` — реализация Runtime API.
- `src/polisyos/core/contracts/runtime.py` — основные runtime DTO.
- `schemas/runtime_api_v1.openapi.json` — канонический контракт для frontend-генерации.
- `tools/runtime/export_runtime_openapi.py` — экспорт OpenAPI.
- `tools/runtime/generate_runtime_client.py` — генерация `runtimeApiClient.ts/js`.
- `frontend/runtime-dashboard/scripts/generate-api-client.sh` — генерация `src/api/types.ts`.

## Локальный запуск

Из корня `policy-engine/` сначала поднимите Runtime API:

```bash
PYTHONPATH=src uv run --extra runtime-http python - <<'PY'
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn

app = create_runtime_api_app()
uvicorn.run(app, host="127.0.0.1", port=8000)
PY
```

Запуск dashboard:

```bash
cd frontend/runtime-dashboard
npm ci
npm run generate:api
npm run dev
```

Запуск reference shell:

```bash
cd frontend/runtime-reference-shell
python -m http.server 4173
```

UI адреса:
- Dashboard: `http://127.0.0.1:5173`
- Reference shell: `http://127.0.0.1:4173`
