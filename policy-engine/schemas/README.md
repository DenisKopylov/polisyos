# schemas — контрактные схемы и снапшоты

Директория `schemas/` хранит зафиксированные контрактные артефакты, которые
используются как стабильная граница между подсистемами (`ir`, `fabric`, `runtime`, `frontend`).

## Роль в системе

`schemas/` реализует Architectural Law C: контракты считаются источником правды.
Здесь лежат не только ABI-снапшоты IR/Fabric, но и соседние контрактные артефакты:

- `snapshots/{ir,fabric}`: JSON Schema для ABI-моделей, проверяемые в pre-commit и CI.
- `snapshots/connectors/contracts.json`: зафиксированные контракты источников данных.
- `runtime_api_v1.openapi.json`: OpenAPI-спецификация Runtime API v1 для генерации фронтенд-клиента.

## Структура директории

```text
schemas/
├── abi_models.py
├── runtime_api_v1.openapi.json
├── __init__.py
└── snapshots/
    ├── ir/
    │   ├── _manifest.json
    │   └── *.schema.json
    ├── fabric/
    │   ├── _manifest.json
    │   └── *.schema.json
    └── connectors/
        └── contracts.json
```

## Архитектура потоков

```text
src/polisyos/ir + src/polisyos/fabric/world
        │
        ▼
schemas/abi_models.py (реестр ABI)
        │
        ▼
tools/diagnostics/gen_schema.py
        │
        ▼
schemas/snapshots/{ir,fabric}
        │
        ├─ pre-commit: abi-schema-check
        └─ CI: .github/workflows/abi.yml + tools/diagnostics/abi_diff.py
```

```text
src/polisyos/fabric/connectors/sources/_contracts/*
        │
        ▼
tools/connectors/check_contracts.py
        │
        ▼
schemas/snapshots/connectors/contracts.json
        │
        ▼
CI: .github/workflows/arch.yml
```

```text
src/polisyos/runtime/http/app.py
        │
        ▼
tools/runtime/export_runtime_openapi.py
        │
        ▼
schemas/runtime_api_v1.openapi.json
        │
        ▼
tools/runtime/generate_runtime_client.py
        ▼
frontend/runtime-api-client/*
```

## Актуальное состояние (в текущем репозитории)

### 1) ABI snapshots (IR + Fabric)

- Реестр: `abi_models.py` (`ABI_MODELS`) — single source of truth.
- Всего ABI-моделей: `34`.
- Разбивка по модулям: `ir=32`, `fabric=2`.
- Приоритеты: `p0=18`, `p1=14`, `p2=2`.
- Текущие `compat_mode`: все записи `strict`.
- `version_field=None` только у: `data_view_request`, `edge_kind`, `node_kind`.

Ключевые P0-домены: Trinity (`trinity_bundle`), governance (`problem_frame`, `policy_spec`, `policy_portfolio`, `model_spec`), norm-system (`norm_pack`, `norm_rule`, `norm_ref`), world/fact/conflict/event модели, а также fabric enum-контракты (`edge_kind`, `node_kind`).

### 2) Connector contracts snapshot

- Файл: `snapshots/connectors/contracts.json`.
- Формат: `version=1`.
- Текущие контракты: `3` (`eurostat.data.generic`, `ukons.datasets.generic`, `worldbank.wdi.generic`).
- Проверка эволюции версий выполняется через `SchemaEvolution` в `tools/connectors/check_contracts.py`.

### 3) Runtime OpenAPI snapshot

- Файл: `runtime_api_v1.openapi.json`.
- OpenAPI: `3.1.0`.
- API title/version: `PolicyOS Runtime API` / `1.0.0`.
- Сейчас описано `15` GET endpoints (runs/debug/artifacts/health surfaces).
- Используется как вход для генерации `frontend/runtime-api-client/runtimeApiClient.{ts,js}`.

## Ключевые модули и особенности

### `abi_models.py`

Реестр ABI-моделей (`ABIModelEntry`) с полями:
`abi_key`, `fqn`, `module`, `schema_file`, `priority`, `compat_mode`,
`version_field`, `lifecycle`, `aliases`, `allow_missing`.

Практически важно:
- Добавление/удаление отслеживаемой ABI-модели делается здесь.
- `select_abi_entries(...)` поддерживает фильтрацию по `abi_key/module/priority/fqn`.

### `snapshots/{ir,fabric}/*`

- Автогенерируемые JSON Schema-файлы + `_manifest.json`.
- `_manifest.json` включает `content_hash`, версии генератора/зависимостей и по-модельные хеши:
  `sha256_full` и `sha256_semantic`.
- Файлы в `snapshots/{ir,fabric}` вручную не редактируются.

### `snapshots/connectors/contracts.json`

- Коммитный baseline контрактов источников данных.
- Валидируется на drift и корректный version bump (major/minor/patch) через `check_contracts.py`.

### `runtime_api_v1.openapi.json`

- Детерминированный экспорт OpenAPI из Runtime FastAPI app.
- Источник для автоматической генерации клиентского SDK в `frontend/runtime-api-client/`.

## Связи с другими директориями

| Директория | Связь |
|---|---|
| `src/polisyos/ir` | Источник Pydantic-контрактов IR для `snapshots/ir` |
| `src/polisyos/fabric/world` | Источник enum ABI (`edge_kind`, `node_kind`) для `snapshots/fabric` |
| `src/polisyos/fabric/connectors/sources/_contracts` | Источник connector contracts для `snapshots/connectors/contracts.json` |
| `src/polisyos/runtime/http` | Источник OpenAPI для `runtime_api_v1.openapi.json` |
| `tools/diagnostics` | Генерация/проверка ABI snapshots (`gen_schema.py`, `abi_diff.py`) |
| `tools/connectors` | Проверка и обновление connector contracts snapshot |
| `tools/runtime` | Экспорт OpenAPI и генерация frontend runtime client |
| `frontend/runtime-api-client` | Потребитель `runtime_api_v1.openapi.json` |
| `.github/workflows/abi.yml` | ABI gate в PR (semantic diff + freshness check) |
| `.github/workflows/arch.yml` | Дополнительный gate: connector contracts + ABI freshness |

## Операционный регламент

Работать из корня `policy-engine/`.

### Обновить ABI snapshots

```bash
python3 tools/diagnostics/gen_schema.py
python3 tools/diagnostics/gen_schema.py --check
```

Для локального сравнения baseline/current:

```bash
python3 tools/diagnostics/gen_schema.py --output-dir /tmp/current_schemas
python3 tools/diagnostics/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --format markdown
```

### Обновить connector contracts snapshot

```bash
python3 tools/connectors/check_contracts.py --check
python3 tools/connectors/check_contracts.py --update
```

### Обновить Runtime OpenAPI + frontend client

```bash
python3 tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
python3 tools/runtime/generate_runtime_client.py \
  --openapi schemas/runtime_api_v1.openapi.json \
  --out-ts frontend/runtime-api-client/runtimeApiClient.ts \
  --out-js frontend/runtime-api-client/runtimeApiClient.js
```

## Правила совместимости ABI (факт по текущей реализации)

- `abi_diff.py` классифицирует `13` типов изменений (`model_added`, `model_removed`, `model_renamed`, `property_*`, `enum_*`, `constraint_changed`, `ref_changed`, `metadata_changed`).
- Для P0 breaking-изменений требуется major bump `schema_version` в формате `MAJOR.MINOR` (например `1.3 -> 2.0`).
- Приоритеты `p1/p2` не блокируют merge, но попадают в warnings.
- Optional-поле в `strict` считается breaking; в `tolerant` может быть совместимым, но учитывается `additionalProperties`.

## Чего не делать

- Не редактировать `snapshots/{ir,fabric}` вручную.
- Не менять `contracts.json` руками, если можно обновить через `check_contracts.py --update`.
- Не обновлять OpenAPI-файл без синхронной регенерации frontend-клиента, если изменился контракт Runtime API.
