# Catalog

`polisyos.fabric.catalog` — слой метрических контрактов и curated binding-правил. Подсистема фиксирует допустимые метрики, их типы/единицы/PII-тиры и связывает метрики с источниками для deterministic retrieval.

## Что дает каталог

- `DataContract` как канонический контракт метрики.
- `MetricBinding` с hash-lock для детекта drift контракта.
- `SourceBinding` для fast-lane маппинга `metric -> connector/dataset/profile`.
- Поиск (`MetricSearcher`) и deterministic resolve (`FastLaneResolver`) для `DataNeed`.

## Состав подсистемы

- `contract.py` — `DataContract`, `DataType`, `Granularity`, `PIITier`, `DataContractCollection`.
- `registry.py` — `DataContractRegistry` и проверка consistency (`ContractNotFoundError`, `ContractHashMismatchError`).
- `binding.py` — `MetricBinding` и `DataContractSchemaBinding`.
- `search.py` — fuzzy/exact поиск метрик.
- `source_bindings.py` — `SourceBindingRegistry` (загрузка/поиск/upsert/persist curated bindings).
- `resolver_fast_lane.py` — `FastLaneResolver`, `FastLaneResolveResult`.
- `validate.py` — загрузка и валидация JSON-коллекций контрактов.

## Типичный flow

1. `DataContractRegistry` загружает curated contracts.
2. `SourceBindingRegistry` загружает curated source bindings.
3. `FastLaneResolver.resolve(...)` строит `FetchPlan` и ранжирует `MetricCandidate`.
4. `retrieval.executor` исполняет plan через connectors.

## Роль в retrieval

`FastLaneResolver` использует:

- контрактные данные (`DataContractRegistry`),
- source bindings (`SourceBindingRegistry`),
- метаданные реестра коннекторов (`ConnectorRegistry.get_metadata(...)`),

чтобы вычислить confidence/trust/freshness и выдать ranked candidates + fallback plans.

## Связи

- `polisyos.fabric.retrieval` — основной потребитель (`resolve`, `search_catalog`, promotion flow).
- `polisyos.fabric.connectors.contracts` — связь contract schema и connector schema.
- governance/quality layers — используют стабильные contract IDs и `PIITier`.
