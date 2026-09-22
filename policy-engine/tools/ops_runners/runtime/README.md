# tools/ops_runners/runtime

Утилиты для контрактов Runtime API и операционных задач по legacy runs.

## Роль в системе

- поддерживать синхронность `Runtime API <-> OpenAPI <-> frontend client`;
- обслуживать инвентаризацию и архив legacy-данных в `runs/`.

## Скрипты

| Скрипт                          | Что делает                                                                          | Где используется      |
| ------------------------------- | ----------------------------------------------------------------------------------- | --------------------- |
| `export_runtime_openapi.py`     | Экспортирует детерминированный OpenAPI JSON (`schemas/runtime_api_v1.openapi.json`) | ручной запуск / релиз |
| `generate_runtime_client.py`    | Низкоуровневая стадия генерации raw TS/JS для package-owned scratch handoff        | package generator |
| `check_runtime_api_contract.py` | Проверяет drift OpenAPI и полного canonical generated family, валидирует инварианты | `ci.yml`          |
| `inventory_legacy_runs.py`      | Инвентаризация `runs/<id>/manifest.json` перед cutover                              | manual/Ops            |
| `archive_legacy_runs.py`        | Детерминированный tar.gz-архив `runs/` + JSON report (опционально удаляет исходник) | manual/Ops            |
| `runtime_state_cleanup.py`      | Dry-run/apply cleanup по зарегистрированным `.polisyos` слотам                      | manual/Ops            |

## Связь с другими директориями

- `src/polisyos/runtime/http/*` (источник OpenAPI)
- `schemas/runtime_api_v1.openapi.json`
- `packages/runtime-api-client/types.ts` и canonicalRuntimeApiClient.{ts,js}
- `runs/*` (legacy manifests и архивирование)

## Типовой запуск

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json
PYTHONPATH=src:. uv run python tools/ops_runners/runtime/inventory_legacy_runs.py --runs-root runs --output _build/.tmp/legacy_runs_inventory.json
uv run python tools/ops_runners/runtime/runtime_state_cleanup.py --slot runs --dry-run
```

## Примечания

- `check_runtime_api_contract.py` по умолчанию проверяет OpenAPI и полный canonical generated family; `--skip-client-drift` оставлен только как совместимый флаг для OpenAPI-only invocations.
- `archive_legacy_runs.py` создает детерминированный архив (нормализованные uid/gid/mtime) для воспроизводимости.
- `runtime_state_cleanup.py` не удаляет `production_data` без `--approve-production-snapshots`.
