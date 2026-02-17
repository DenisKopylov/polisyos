# Retrieval

`polisyos.fabric.retrieval` — гибридный слой разрешения и выполнения data-needs: FastLane (curated bindings), ExploreLane (живое discovery), execution with preview gate и fallback.

## Роль в системе

```text
DataResolveRequest
   -> RetrievalService.resolve()
      -> FastLaneResolver (+ optional ExploreLane fallback)
   -> FetchPlan[]
   -> RetrievalService.execute_fetch_plans()
   -> DataContext (metrics + previews + promotion signals)
```

Подсистема используется control/NL потоками, когда нужно получить данные по метрике, а не напрямую по `connector_id:dataset_id`.

## Основные компоненты

### `service.py`

- `RetrievalService` оркестрирует `resolve`, `discover`, `preview`, `execute_fetch_plans`.
- Хранит local discovery index и promotion queue.

### `executor.py`

- `FetchExecutor` выполняет preview gate (`quality_min`) и полный fetch.
- Поддерживает fallback цепочку `FetchPlanFallback`.

### `explore_lane.py`

- `ExploreLaneDiscovery` выполняет bounded discovery через `list_datasets(...)`.
- Применяет лимиты (`time_budget_ms`, `max_candidates_total`, `max_sources_per_query`).

## Логика разрешения

1. FastLane: deterministic resolve по `catalog/source_bindings`.
2. ExploreLane (опционально): live-discovery для unresolved метрик.
3. Построение `FetchPlan` с fallback источниками.
4. Preview gate перед full fetch.
5. Опциональная постановка promotion candidates (для последующего upsert в `SourceBindingRegistry`).

## Feature flags

- `POLISYOS_RETRIEVAL_FASTLANE_ENABLED`
- `POLISYOS_RETRIEVAL_EXPLORE_ENABLED`
- `POLISYOS_RETRIEVAL_PROMOTION_ENABLED`
- `POLISYOS_RETRIEVAL_PROMOTION_PERSIST`

## Связи

- `fabric.catalog.resolver_fast_lane` и `fabric.catalog.source_bindings` — deterministic кандидаты и планы.
- `fabric.connectors.registry` и `fabric.connectors.profiles` — реальный fetch/discovery.
- `polisyos.core.contracts.control` — `DataNeed`, `FetchPlan`, `DataContext`, `PromotionCandidate`.
