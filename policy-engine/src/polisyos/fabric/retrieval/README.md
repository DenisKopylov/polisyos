# Retrieval

`polisyos.fabric.retrieval` — слой resolve+execute для `DataNeed`: сначала строит `FetchPlan`, затем выполняет preview/full fetch с fallback.

## Логика lane-ов

```text
DataResolveRequest
  -> FastLane (catalog/source_bindings)
  -> optional DatasetCatalog lane (если передан dataset_catalog)
  -> optional ExploreLane (bounded live discovery)
  -> FetchPlan[] (+ fallbacks)
  -> execute_fetch_plans
  -> DataContext + previews + promotion signals
```

## Основные компоненты

- [service.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/service.py)
  `RetrievalService`: `resolve`, `discover`, `preview`, `execute_fetch_plans`, `search_catalog`, index stats, promotion queue management.
- [executor.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/executor.py)
  `FetchExecutor`: preview gate по `quality_min`, full fetch, fallback chain (`FetchPlanFallback`).
- [explore_lane.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/explore_lane.py)
  `ExploreLaneDiscovery`: live discovery через `list_datasets(...)` с бюджетами времени/кандидатов/источников.

## Promotion и local index

`RetrievalService` поддерживает:

- локальный discovery index (docs total / size / coverage по источникам),
- очередь promotion candidates,
- ручные действия `approve_promotion(...)` / `reject_promotion(...)`,
- optional persist promoted bindings в `SourceBindingRegistry`.

## Feature flags

- `POLISYOS_RETRIEVAL_FASTLANE_ENABLED`
- `POLISYOS_RETRIEVAL_EXPLORE_ENABLED`
- `POLISYOS_RETRIEVAL_PROMOTION_ENABLED`
- `POLISYOS_RETRIEVAL_PROMOTION_PERSIST`

## Связи

- `fabric.catalog.resolver_fast_lane` и `fabric.catalog.source_bindings` — deterministic resolve.
- `fabric.connectors.registry` + `fabric.connectors.profiles` — runtime fetch/discovery.
- `polisyos.core.contracts.control` — `DataNeed`, `FetchPlan`, `DataContext`, `PromotionCandidate`.
