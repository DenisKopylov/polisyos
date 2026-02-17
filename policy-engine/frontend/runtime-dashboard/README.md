# `runtime-dashboard` — основной frontend Runtime API

`runtime-dashboard` это React/TypeScript приложение для runtime-наблюдаемости и control-plane операций.

## Что покрывает UI

| Route | Назначение |
| --- | --- |
| `/` | Runtime overview: статусы, тренды, failed runs, быстрые переходы |
| `/runs` | Run explorer с фильтрами и cursor pagination |
| `/runs/:runId` | Детальная карточка run (tabs: timeline, nodes, lineage, agents/models, workflow, governance, debug, decision) |
| `/artifacts/:artifactId` | Artifact inspector (content/schema/lineage + специализированные viewers для decision/trinity/simulation) |
| `/launch` | Запуск run: `workflow` и `natural-language` режимы |
| `/sources` | Каталог source profiles + ingest выбранного источника |
| `/data` | Data Intelligence (resolve/discover/preview/promotion) + connectors/cache + ingest |
| `/lex` | Запуск/мониторинг Lex pipeline, graph stats и semantic search |
| `/health` | Техническая health-панель API |

## Архитектура модулей

См. детализацию в `src/README.md`.

Ключевые зоны:
- `src/pages/*` — route-level сценарии.
- `src/api/*` — API слой (`openapi-fetch`, query keys, hooks, validators, error normalization).
- `src/components/*` — UI-компоненты по доменам (`agents`, `workflow`, `governance`, `simulation`, `data`, `trinity`).
- `src/lib/domain/*` — адаптеры payload -> view-model для сложных артефактов.

## API и контрактная стратегия

- Транспорт: `openapi-fetch` (`src/api/client.ts`).
- Типы: `src/api/types.ts` (генерируется из `schemas/runtime_api_v1.openapi.json`).
- Кэш и состояние: React Query (`queryKeys`, invalidate после mutation).
- Ошибки: единый `RuntimeApiRequestError` (`src/api/http.ts`).
- Валидация:
  - runtime read-paths валидируются через `zod` (`src/api/validators.ts`);
  - control-plane endpoints используют OpenAPI-typed payloads.

## Команды

```bash
npm install
npm run generate:api
npm run typecheck
npm run build
npm run dev
```

Дополнительно:

```bash
npm run preview
npm run dev:mock
```

`dev:mock` только выставляет `VITE_USE_MOCKS=true`; встроенных mock-handlers в репозитории нет.

## Генерация API типов

```bash
./scripts/generate-api-client.sh
```

Скрипт:
- читает `schemas/runtime_api_v1.openapi.json`;
- обновляет `frontend/runtime-dashboard/src/api/types.ts`.

## Конфигурация Runtime API

- Vite proxy по умолчанию: `http://127.0.0.1:8000`.
- Переменная `RUNTIME_API_URL` меняет proxy target в dev-сервере.
- Переменная `VITE_RUNTIME_API_URL` задает базовый URL напрямую для `openapi-fetch`.

## Ограничения

- Нет встроенного auth-flow и UI для пользовательских заголовков.
- Нет persisted UI state между перезапусками.
- Часть control-plane payloads рендерится best-effort (без доменной валидации уровня runtime validators).
