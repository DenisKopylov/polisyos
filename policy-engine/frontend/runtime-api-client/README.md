# `runtime-api-client` — сгенерированный клиент Runtime API v1

`runtime-api-client` хранит артефакты, которые генерируются из OpenAPI-схемы Runtime API.  
Ручное редактирование `runtimeApiClient.ts/js` не предполагается.

## Что лежит в директории

- `runtimeApiClient.ts` — typed TypeScript-клиент + экспорт типов контрактов API.
- `runtimeApiClient.js` — ESM-клиент для браузера/JS-runtime без TypeScript.

## Источник истины

Контракт клиента формируется цепочкой:

```text
Runtime API app -> OpenAPI schema -> generated client
```

Технически это:
- `tools/runtime/export_runtime_openapi.py`
- `schemas/runtime_api_v1.openapi.json`
- `tools/runtime/generate_runtime_client.py`

## Покрытие API (текущие группы методов)

- Health: `health`, `ready`, `runtimeApiHealth`.
- Runs: `listRuns`, `getRunDetails`, `getRunTimeline`, `getRunNodes`, `getRunLineage`.
- Debug: `getNodeDebug`, `getGovernanceDebug`, `getRunErrors`.
- Artifacts: `getArtifactManifest`, `getArtifactContent`, `getArtifactLineage`, `getArtifactSchema`.

## Поведение и ограничения

- Клиент нормализует `baseUrl` (убирает завершающий `/`).
- Query-параметры сериализуются с поддержкой массивов и `Date -> ISO`.
- На non-2xx ответах бросается `Error` со статусом и телом ответа.
- Retry/circuit-breaker/auth-flow не встроены; для кастомизации доступны `headers` и `fetchImpl` в `RuntimeApiClientOptions`.
- Клиент поддерживает read-only HTTP-поверхность Runtime API v1.

## Регенерация

Из корня `policy-engine/`:

```bash
PYTHONPATH=src uv run python tools/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json

PYTHONPATH=src uv run python tools/runtime/generate_runtime_client.py \
  --openapi schemas/runtime_api_v1.openapi.json \
  --out-ts frontend/runtime-api-client/runtimeApiClient.ts \
  --out-js frontend/runtime-api-client/runtimeApiClient.js
```

Генерация детерминированная: одинаковый OpenAPI-вход должен давать byte-stable результат.

Проверить drift OpenAPI/клиента и контрактные инварианты:

```bash
PYTHONPATH=src uv run python tools/runtime/check_runtime_api_contract.py
```
