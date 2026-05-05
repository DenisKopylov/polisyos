# schemas — контрактный baseline Policy Engine

`schemas/` хранит фиксированные контрактные артефакты между слоями `ir`, `fabric`, `runtime` и клиентами. Эти файлы используются в CI для drift/compatibility checks и не должны меняться вручную вне генераторов.

## Что находится в директории

| Артефакт                                                       | Назначение                                                                    |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `abi_models.py`                                                | Реестр ABI (`ABI_MODELS`): что и как версионируется в `snapshots/{ir,fabric}` |
| `snapshots/ir/*.schema.json`, `snapshots/fabric/*.schema.json` | JSON Schema baseline для semantic diff                                        |
| `snapshots/*/_manifest.json`                                   | Метаданные генерации и хеши (`sha256_full`, `sha256_semantic`)                |
| `snapshots/connectors/contracts.json`                          | Snapshot контрактов source-коннекторов                                        |
| `runtime_api_v1.openapi.json`                                  | Коммитный OpenAPI контракт Runtime API v1                                     |

## Актуальное состояние (2026-03-03)

- ABI registry: `50` активных моделей (`ir=48`, `fabric=2`), все в `compat_mode=strict`.
- Приоритеты ABI: `p0=18`, `p1=23`, `p2=9`.
- `version_field=None` у `certification_result`, `data_view_request`, `outer_search_result`, `edge_kind`, `node_kind`.
- ABI manifests:
  - `snapshots/ir/_manifest.json`: `generated_at=2026-03-03T16:49:25+00:00`;
  - `snapshots/fabric/_manifest.json`: `generated_at=2026-03-02T16:48:08+00:00`.
- Connector snapshot: `version=1`, контрактов `3` (`eurostat.data.generic`, `ukons.datasets.generic`, `worldbank.wdi.generic`).
- Runtime OpenAPI: `openapi=3.1.0`, `PolicyOS Runtime API 1.0.0`, `37` операций (`27 GET`, `10 POST`).
- `tools/ops/runtime/generate_runtime_client.py` генерирует клиент только по `GET`; типы для полного OpenAPI генерируются отдельно в `frontend/runtime-dashboard/src/api/types.ts`.

## Архитектурные потоки

```text
src/polisyos/ir/** + src/polisyos/ir/world/abi.py
  -> schemas/abi_models.py
  -> tools/quality/diagnostics/gen_schema.py
  -> schemas/snapshots/{ir,fabric}
  -> ABI checks: .github/workflows/abi.yml + .github/workflows/ci.yml
```

```text
src/polisyos/fabric/connectors/sources/_contracts/*
  -> polisyos-tools connectors check-contracts
  -> schemas/snapshots/connectors/contracts.json
  -> arch check: .github/workflows/ci.yml
```

```text
src/polisyos/runtime/http/app.py
  -> tools/ops/runtime/export_runtime_openapi.py
  -> schemas/runtime_api_v1.openapi.json
  -> tools/ops/runtime/check_runtime_api_contract.py
  -> tools/ops/runtime/generate_runtime_client.py -> frontend/runtime-api-client/*
  -> frontend/runtime-dashboard/scripts/generate-api-client.sh -> frontend/runtime-dashboard/src/api/types.ts
```

## Связи с соседними директориями

| Директория                                          | Роль относительно `schemas/`                                            |
| --------------------------------------------------- | ----------------------------------------------------------------------- |
| `src/polisyos/ir`                                   | Источник Pydantic ABI-моделей для `snapshots/ir`                        |
| `src/polisyos/ir/world/abi.py`                      | Источник enum ABI (`edge_kind`, `node_kind`) для `snapshots/fabric`     |
| `src/polisyos/fabric/connectors/sources/_contracts` | Источник connector-контрактов для `snapshots/connectors/contracts.json` |
| `src/polisyos/runtime/http`                         | Источник OpenAPI контракта для `runtime_api_v1.openapi.json`            |
| `tools/quality/diagnostics`                                 | Генерация ABI snapshot и semantic diff (`gen_schema.py`, `abi_diff.py`) |
| `tools/devx/connectors`                             | Drift/compatibility проверка и обновление connector snapshot            |
| `tools/ops/runtime`                                     | Экспорт OpenAPI, hardening+drift checks, генерация runtime клиента      |
| `frontend/runtime-api-client`                       | Коммитный runtime SDK (TS/JS)                                           |
| `frontend/runtime-dashboard`                        | Генерация OpenAPI типов для UI (`npm run generate:api`)                 |

## Рабочие команды (из `policy-engine/`)

```bash
# Проверка baseline без изменений
PYTHONPATH=src:. uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check
uv run polisyos-tools connectors check-contracts --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py
```

```bash
# Обновление baseline
PYTHONPATH=src:. uv run --extra ml python tools/quality/diagnostics/gen_schema.py
uv run polisyos-tools connectors check-contracts --update
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js
```

```bash
# Синхронизация UI типов
cd frontend/runtime-dashboard
npm run generate:api
```

```bash
# Локальный semantic diff ABI (перед PR)
python3 tools/quality/diagnostics/gen_schema.py --output-dir /tmp/current_schemas
python3 tools/quality/diagnostics/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --format markdown
```

## Инварианты сопровождения

- Не редактировать вручную файлы в `snapshots/ir` и `snapshots/fabric`.
- Не редактировать вручную `snapshots/connectors/contracts.json`, использовать `check_contracts.py --update`.
- Любое изменение Runtime API сопровождается синхронным обновлением:
  - `schemas/runtime_api_v1.openapi.json`,
  - `frontend/runtime-api-client/runtimeApiClient.ts` и `runtimeApiClient.js`,
  - `frontend/runtime-dashboard/src/api/types.ts`.

## Подробности по подпапкам

- `schemas/snapshots/README.md`
- `schemas/snapshots/ir/README.md`
- `schemas/snapshots/fabric/README.md`
- `schemas/snapshots/connectors/README.md`
