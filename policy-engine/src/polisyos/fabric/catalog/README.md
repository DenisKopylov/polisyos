# Catalog

`polisyos.fabric.catalog` — метрический каталог контрактов, который фиксирует допустимые метрики и защищает верхний слой от "галлюцинаций" имен, типов и единиц.

## Что дает каталог

- Канонический `DataContract` на метрику
- `MetricBinding` с hash-lock (детектирует drift контракта)
- Fuzzy/exact поиск по aliases/tags/display name
- Проверку актуальности binding через `DataContractRegistry.validate_binding(...)`

## Состав

- `contract.py` — `DataContract`, `DataType`, `Granularity`, `PIITier`, `DataContractCollection`
- `binding.py` — `MetricBinding` + `DataContractSchemaBinding` (связка контракта со schema field)
- `registry.py` — `DataContractRegistry`, hash-validation, ошибки `ContractNotFoundError`/`ContractHashMismatchError`
- `search.py` — `MetricSearcher`, `SearchResult`, `SearchResponse`
- `validate.py` — загрузка и валидация JSON-коллекции контрактов

## Типичный сценарий

1. Загрузить registry из curated каталога.
2. Найти метрику через `MetricSearcher`.
3. Зафиксировать `MetricBinding`.
4. Перед использованием проверить binding против текущего контракта.

## Связи

- `polisyos.scientist` — получает типобезопасный binding вместо сырых метрик
- `connectors.contracts` — `DataContractSchemaBinding` использует schema registry/field specs
- `quality_gate`/governance слои — используют стабильные contract IDs и pii tiers
