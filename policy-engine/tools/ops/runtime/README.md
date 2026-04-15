# tools/runtime

Утилиты для контрактов Runtime API и операционных задач по legacy runs.

## Роль в системе

- поддерживать синхронность `Runtime API <-> OpenAPI <-> frontend client`;
- обслуживать инвентаризацию и архив legacy-данных в `runs/`.

## Скрипты

| Скрипт | Что делает | Где используется |
|---|---|---|
| `export_runtime_openapi.py` | Экспортирует детерминированный OpenAPI JSON (`schemas/runtime_api_v1.openapi.json`) | ручной запуск / релиз |
| `generate_runtime_client.py` | Генерирует TS/JS клиента в `frontend/runtime-api-client/` | ручной запуск / релиз |
| `check_runtime_api_contract.py` | Проверяет drift OpenAPI и runtime client, валидирует инварианты runtime-контракта | `ci.yml` |
| `inventory_legacy_runs.py` | Инвентаризация `runs/<id>/manifest.json` перед cutover | manual/Ops |
| `archive_legacy_runs.py` | Детерминированный tar.gz-архив `runs/` + JSON report (опционально удаляет исходник) | manual/Ops |

## Связь с другими директориями

- `src/polisyos/runtime/http/*` (источник OpenAPI)
- `schemas/runtime_api_v1.openapi.json`
- `frontend/runtime-api-client/runtimeApiClient.{ts,js}`
- `runs/*` (legacy manifests и архивирование)

## Типовой запуск

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js
PYTHONPATH=src:. uv run python tools/runtime/inventory_legacy_runs.py --runs-root runs --output .tmp/legacy_runs_inventory.json
```

## Примечания

- `check_runtime_api_contract.py` по умолчанию проверяет и OpenAPI, и generated client; отключение client drift: `--skip-client-drift`.
- `archive_legacy_runs.py` создает детерминированный архив (нормализованные uid/gid/mtime) для воспроизводимости.
