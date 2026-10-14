# schemas — контрактный baseline Policy Engine

`schemas/` хранит фиксированные контрактные артефакты между слоями `ir`, `fabric`, `runtime` и клиентами. Эти файлы используются в CI для drift/compatibility checks и не должны меняться вручную вне генераторов.

## Что находится в директории

| Артефакт                                                       | Назначение                                                     |
| -------------------------------------------------------------- | -------------------------------------------------------------- |
| `snapshots/ir/*.schema.json`, `snapshots/fabric/*.schema.json` | JSON Schema baseline для semantic diff                         |
| `snapshots/*/_manifest.json`                                   | Метаданные генерации и хеши (`sha256_full`, `sha256_semantic`) |
| `snapshots/connectors/contracts.json`                          | Snapshot контрактов source-коннекторов                         |
| `runtime_api_v1.openapi.json`                                  | Коммитный OpenAPI контракт Runtime API v1                      |

Кодовый ABI registry находится в `src/polisyos/schemas/abi_models.py`; эта
директория остается только для JSON/YAML/OpenAPI snapshot артефактов.

## Где проверять текущее состояние

Эта страница описывает расположение контрактов, а не публикует единый
инвентарь их текущих размеров и версий. Для владельцев, статусов и committed
outputs используйте [каталог generated artifacts](../docs/reference/generated-artifacts.md)
и его [исходный реестр](../architecture/generated_artifacts.toml). Для конкретного
значения сверяйте соответствующий исходный контракт и snapshot или manifest.

- Кодовый ABI registry: `src/polisyos/schemas/abi_models.py`; ABI snapshots и
  manifests: `snapshots/ir/` и `snapshots/fabric/`.
- Source connector contracts: `src/polisyos/fabric/connectors/sources/_contracts/`;
  committed snapshot: `snapshots/connectors/contracts.json`.
- Runtime API source: `src/polisyos/runtime/http/`; committed OpenAPI snapshot:
  `runtime_api_v1.openapi.json`.

Это разные наборы с разными знаменателями: число моделей в registry нельзя
считать числом schema-файлов в snapshot, а число connector definitions — числом
операций OpenAPI. При публикации любого количества или версии указывайте точный
артефакт и его собственную версию или generation metadata; не объединяйте их в
один «актуальный» счетчик.

`packages/runtime-api-client` owns the full generated client chain; its
low-level renderer writes only to a caller-provided private scratch path,
while `types.ts` and the canonical TS/JS client are the committed outputs.

## Архитектурные потоки

```text
src/polisyos/ir/** + src/polisyos/ir/world/abi.py
  -> src/polisyos/schemas/abi_models.py
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
  -> tools/ops_runners/runtime/export_runtime_openapi.py
  -> schemas/runtime_api_v1.openapi.json
  -> tools/ops_runners/runtime/check_runtime_api_contract.py
  -> packages/runtime-api-client/scripts/generate-runtime-api-client.sh
  -> packages/runtime-api-client/{types.ts,canonicalRuntimeApiClient.ts,canonicalRuntimeApiClient.js}
  -> apps/runtime-dashboard/scripts/generate-api-client.sh -> apps/runtime-dashboard/src/api/types.ts
```

## Связи с соседними директориями

| Директория                                          | Роль относительно `schemas/`                                            |
| --------------------------------------------------- | ----------------------------------------------------------------------- |
| `src/polisyos/ir`                                   | Источник Pydantic ABI-моделей для `snapshots/ir`                        |
| `src/polisyos/ir/world/abi.py`                      | Источник enum ABI (`edge_kind`, `node_kind`) для `snapshots/fabric`     |
| `src/polisyos/fabric/connectors/sources/_contracts` | Источник connector-контрактов для `snapshots/connectors/contracts.json` |
| `src/polisyos/runtime/http`                         | Источник OpenAPI контракта для `runtime_api_v1.openapi.json`            |
| `tools/quality/diagnostics`                         | Генерация ABI snapshot и semantic diff (`gen_schema.py`, `abi_diff.py`) |
| `tools/devx/connectors`                             | Drift/compatibility проверка и обновление connector snapshot            |
| `tools/ops_runners/runtime`                         | Экспорт OpenAPI, hardening+drift checks, генерация runtime клиента      |
| `packages/runtime-api-client`                       | Коммитный runtime SDK (TS/JS)                                           |
| `apps/runtime-dashboard`                            | Генерация OpenAPI типов для UI (`corepack pnpm run generate:api`)       |

## Рабочие команды (из `policy-engine/`)

```bash
# Проверка baseline без изменений
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run polisyos-tools connectors check-contracts --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
```

```bash
# Обновление baseline
uv run --extra ml polisyos-tools diagnostics gen-schema
uv run polisyos-tools connectors check-contracts --update
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json
```

```bash
# Синхронизация UI типов
cd apps/runtime-dashboard
corepack pnpm run generate:api
```

```bash
# Локальный semantic diff ABI (перед PR)
uv run --extra ml polisyos-tools diagnostics gen-schema --output-dir /tmp/current_schemas
python3 tools/quality/diagnostics/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --format markdown
```

## Инварианты сопровождения

- Не добавлять Python modules/package markers в `schemas/`; product imports идут
  через `polisyos.*`, а не через `import schemas`.
- Не редактировать вручную файлы в `snapshots/ir` и `snapshots/fabric`.
- Не редактировать вручную `snapshots/connectors/contracts.json`, использовать `check_contracts.py --update`.
- Любое изменение Runtime API сопровождается синхронным обновлением:
  - `schemas/runtime_api_v1.openapi.json`,
  - `packages/runtime-api-client/types.ts` и canonical TS/JS client,
  - `apps/runtime-dashboard/src/api/types.ts`.

## Подробности по подпапкам

- `schemas/snapshots/README.md`
- `schemas/snapshots/ir/README.md`
- `schemas/snapshots/fabric/README.md`
- `schemas/snapshots/connectors/README.md`
