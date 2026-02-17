# schemas — контрактные артефакты Policy Engine

`schemas/` фиксирует публичные контракты между подсистемами (`ir`, `fabric`, `runtime`, `frontend`) и используется как baseline для drift/compatibility проверок в CI.

## Что хранится в директории

| Артефакт | Роль |
| --- | --- |
| `abi_models.py` | Реестр ABI моделей (`ABI_MODELS`), которые должны быть отслежены снапшотами |
| `snapshots/ir/*`, `snapshots/fabric/*` | Детерминированные JSON Schema снапшоты ABI для semantic diff |
| `snapshots/connectors/contracts.json` | Зафиксированные контракты источников данных для connector layer |
| `runtime_api_v1.openapi.json` | Зафиксированная OpenAPI v1 спецификация Runtime API |

## Актуальное состояние (по состоянию на 2026-02-17)

- ABI registry: `34` моделей (`ir=32`, `fabric=2`), все `active`, все `compat_mode=strict`.
- Приоритеты ABI: `p0=18`, `p1=14`, `p2=2`.
- `version_field=None` у `data_view_request`, `edge_kind`, `node_kind`.
- ABI манифесты: `snapshots/ir/_manifest.json` (`generated_at=2026-02-08T18:29:42+00:00`), `snapshots/fabric/_manifest.json` (`generated_at=2026-02-07T12:16:56+00:00`).
- Connector snapshot: `version=1`, `3` контракта (`eurostat.data.generic`, `ukons.datasets.generic`, `worldbank.wdi.generic`).
- Runtime OpenAPI: `openapi=3.1.0`, `PolicyOS Runtime API 1.0.0`, `37` операций (`27 GET`, `10 POST`).
- `tools/runtime/generate_runtime_client.py` генерирует SDK только для `GET`-операций; типы для всего контракта дополнительно генерируются в `frontend/runtime-dashboard/src/api/types.ts`.

## Архитектура и потоки

```text
src/polisyos/ir + src/polisyos/fabric/world
  -> schemas/abi_models.py
  -> tools/diagnostics/gen_schema.py
  -> schemas/snapshots/{ir,fabric}
  -> CI: .github/workflows/abi.yml + .github/workflows/arch.yml
```

```text
src/polisyos/fabric/connectors/sources/_contracts/*
  -> tools/connectors/check_contracts.py
  -> schemas/snapshots/connectors/contracts.json
  -> CI: .github/workflows/arch.yml
```

```text
src/polisyos/runtime/http/app.py
  -> tools/runtime/export_runtime_openapi.py
  -> schemas/runtime_api_v1.openapi.json
  -> tools/runtime/generate_runtime_client.py -> frontend/runtime-api-client/*
  -> frontend/runtime-dashboard/scripts/generate-api-client.sh -> frontend/runtime-dashboard/src/api/types.ts
```

## Связи с другими директориями

| Директория | Связь |
| --- | --- |
| `src/polisyos/ir` | Источник Pydantic ABI-моделей для `snapshots/ir` |
| `src/polisyos/fabric/world` | Источник enum ABI (`edge_kind`, `node_kind`) для `snapshots/fabric` |
| `src/polisyos/fabric/connectors/sources/_contracts` | Источник connector контрактов для `snapshots/connectors/contracts.json` |
| `src/polisyos/runtime/http` | Источник OpenAPI контракта для `runtime_api_v1.openapi.json` |
| `tools/diagnostics` | Генерация/проверка ABI (`gen_schema.py`, `abi_diff.py`) |
| `tools/connectors` | Проверка и обновление snapshot контрактов коннекторов |
| `tools/runtime` | Экспорт OpenAPI, drift-check, генерация runtime-api клиента |
| `.github/workflows/abi.yml` | PR-gate для ABI semantic diff и freshness |
| `.github/workflows/arch.yml` | Общий архитектурный gate, включая ABI/connectors/runtime API проверки |

## Локальная работа (из корня `policy-engine/`)

### Проверка контрактов без изменений

```bash
python3 tools/diagnostics/gen_schema.py --check
python3 tools/connectors/check_contracts.py --check
python3 tools/runtime/check_runtime_api_contract.py
```

### Обновление baseline артефактов

```bash
python3 tools/diagnostics/gen_schema.py
python3 tools/connectors/check_contracts.py --update
python3 tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
python3 tools/runtime/generate_runtime_client.py \
  --openapi schemas/runtime_api_v1.openapi.json \
  --out-ts frontend/runtime-api-client/runtimeApiClient.ts \
  --out-js frontend/runtime-api-client/runtimeApiClient.js
```

```bash
cd frontend/runtime-dashboard
npm run generate:api
```

### Локальный semantic diff ABI

```bash
python3 tools/diagnostics/gen_schema.py --output-dir /tmp/current_schemas
python3 tools/diagnostics/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --format markdown
```

## Инварианты сопровождения

- Не редактировать вручную `snapshots/ir/*.json` и `snapshots/fabric/*.json`.
- Не править вручную `snapshots/connectors/contracts.json`, если можно использовать `check_contracts.py --update`.
- При изменении Runtime API синхронно обновлять `schemas/runtime_api_v1.openapi.json`, `frontend/runtime-api-client/*` и `frontend/runtime-dashboard/src/api/types.ts`.

## Подробности по подпапкам

- `schemas/snapshots/README.md`
- `schemas/snapshots/ir/README.md`
- `schemas/snapshots/fabric/README.md`
- `schemas/snapshots/connectors/README.md`
