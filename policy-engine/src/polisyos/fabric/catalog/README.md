# Catalog

`polisyos.fabric.catalog` — слой метрических контрактов и curated source bindings для deterministic resolve.

## Что решает каталог

- фиксирует канонические метрики (`DataContract`) и их тип/единицы/PII-tier;
- дает hash-locked представление метрики (`MetricBinding`) для детекта contract drift;
- хранит curated mapping `metric -> connector/dataset/profile` (`SourceBinding`);
- предоставляет search и fast-lane resolve для retrieval.

## Состав

- `contract.py` — `DataContract`, `DataType`, `Granularity`, `PIITier`, `DataContractCollection`.
- `registry.py` — `DataContractRegistry`, `ContractNotFoundError`, `ContractHashMismatchError`.
- `binding.py` — `MetricBinding`, `DataContractSchemaBinding`.
- `source_bindings.py` — `SourceBinding`, `SourceBindingRegistry`.
- `search.py` — `MetricSearcher`, `SearchResponse`.
- `resolver_fast_lane.py` — `FastLaneResolver`, `FastLaneResolveResult`.
- `validate.py` — загрузка и schema validation контрактных JSON.

## Типичный flow

1. `DataContractRegistry` читает curated `data_contracts.json`.
2. `SourceBindingRegistry` читает curated `source_bindings.json`.
3. `FastLaneResolver.resolve(...)` ранжирует кандидатов и строит `FetchPlan` + fallbacks.
4. `retrieval.executor` выполняет план через connectors.

## Связи

- `fabric.retrieval` — основной consumer для fastlane/search/promotions.
- `fabric.connectors.contracts` — привязка metric contract к dataset schema.
- governance/security — используют стабильные `metric_id` и `PIITier`.
