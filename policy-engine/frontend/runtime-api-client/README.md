# `runtime-api-client` — сгенерированный JS/TS клиент Runtime API v1

`runtime-api-client` содержит auto-generated артефакты по OpenAPI-контракту.
Ручное редактирование `runtimeApiClient.ts` и `runtimeApiClient.js` не предусмотрено.

## Содержимое

- `runtimeApiClient.ts` — typed TypeScript-клиент и типы ответов.
- `runtimeApiClient.js` — ESM-клиент для runtime без TypeScript.

Основной потребитель в этом репозитории: `frontend/runtime-reference-shell/app.js`.

## Источник истины и генерация

```text
Runtime API app -> schemas/runtime_api_v1.openapi.json -> generated runtimeApiClient.ts/js
```

Цепочка:
- `tools/runtime/export_runtime_openapi.py`
- `schemas/runtime_api_v1.openapi.json`
- `tools/runtime/generate_runtime_client.py`

## Актуальное покрытие методов

Клиент генерирует GET/read-path wrappers по группам:
- health: `runtimeApiHealth`, `health`, `ready`;
- runs: `listRuns`, `getRunDetails`, `getRunTimeline`, `getRunNodes`, `getRunLineage`, `getRunAgents`;
- debug: `getNodeDebug`, `getGovernanceDebug`, `getRunErrors`, `getRunFeedback`, `getRunCompare`;
- artifacts: `getArtifactManifest`, `getArtifactContent`, `getArtifactLineage`, `getArtifactSchema`;
- control (read): `listBindingProfiles`, `getCacheStatus`, `searchDataCatalog`, `listConnectors`, `getDataIndexStats`, `listSourceProfiles`, `listDataPromotionCandidates`, `listLlmProfiles`.

## Поведение и ограничения

- Нормализует `baseUrl` (удаляет завершающий `/`).
- Сериализует query-параметры, включая массивы и `Date -> ISO`.
- На non-2xx кидает `Error` с HTTP-статусом и body.
- Не включает retry/circuit-breaker/auth-flow; настройка только через `headers` и `fetchImpl`.
- Это thin client поверх контрактных GET endpoint-ов; POST/управляющие сценарии dashboard реализует через `openapi-fetch` в `runtime-dashboard`.

## Регенерация

Из корня `policy-engine/`:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json

PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/generate_runtime_client.py \
  --openapi schemas/runtime_api_v1.openapi.json \
  --out-ts frontend/runtime-api-client/runtimeApiClient.ts \
  --out-js frontend/runtime-api-client/runtimeApiClient.js
```

Проверка drift и контрактных инвариантов:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
```
