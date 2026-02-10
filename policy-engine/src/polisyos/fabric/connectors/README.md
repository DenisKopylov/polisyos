# Connectors

`polisyos.fabric.connectors` — подсистема подключения к внешним источникам данных. Она задает протокол коннекторов, runtime-реестр, resilience/caching/validation слои и инструменты композиции результатов.

## Роль в Fabric

```text
ConnectorRegistry -> SourceConnector.fetch -> (cache/resilience/contracts/quality/transform) -> FetchResult
```

Эта подсистема используется в:

- `polisyos.fabric.ingestion.run_connectors_ingestion`
- `polisyos.fabric._connector_bridge.fabric_get_data`

## Архитектура

### Протокол и базовые абстракции

- `base.py`
- `SourceConnector` (Protocol)
- `ConnectionConfig`, `ConnectionHandle`, `HealthStatus`
- `BaseConnector` с capability-gated default-реализациями

### Runtime управление

- `registry.py` / `registry_core_parts.py` — `ConnectorRegistry` (singleton, lazy-loading, индексы, lifecycle)
- `pool.py` — connection pooling
- `discovery.py` — discovery builtin/entrypoint/explicit connectors
- `capabilities.py` — capability decorators и protocol compliance checks
- `validation.py` — schema validation/coercion для `FetchResult`

### Основные подсистемы

- `cache/` — CAS-кэш, политики TTL/LRU/size/smart, invalidation, prefetch, proxy
- `resilience/` — retry, circuit breaker, rate limiter, fallback, unified `apply_resilience`
- `contracts/` — DataSchema, inference, evolution, registry, validating proxy
- `quality/` — freshness/completeness/consistency и quality reports
- `transform/` — конвейер преобразований (normalization/harmonization/aggregation/imputation/filter/validation)
- `types/` — dimensional, units, temporal, coercion + connector errors/types
- `federation/` — planner/ranker/resolver/composer + merge log + evidence aggregation
- `testing/` — harness/simulator/fault injection/contract assertions

### Реализации источников

- `sources/` — production connectors (`WorldBankConnector`, `EurostatConnector`, `UKONSConnector`)
- `reference/` — reference connectors (`StaticCSVConnector`, `GenericRESTConnector`, `SDMXConnector`)

## Минимальный путь использования

1. Получить/инициализировать реестр: `ConnectorRegistry.get_instance()`
2. Получить коннектор: `registry.get("world_bank")`
3. Выполнить fetch (обычно через `ingestion` или `fabric_get_data`, а не напрямую)

## Связи с другими модулями

- `polisyos.ir.connectors` — канонические контракты `FetchRequest/FetchResult`, `ConnectorCapability`, `DataVersion`
- `polisyos.fabric.ingestion` — orchestration ingestion pipeline
- `polisyos.fabric.evidence` и `polisyos.fabric.provenance` — фиксация трассируемости
