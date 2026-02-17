# Connectors

`polisyos.fabric.connectors` — подсистема интеграции с внешними источниками данных. Она определяет протоколы коннекторов, runtime-реестр, connection lifecycle, а также слои надежности/валидации/качества вокруг `fetch`.

## Роль в Fabric

```text
ConnectorRegistry -> SourceConnector.fetch/list_datasets -> FetchResult
                     + cache/resilience/contracts/quality/transform/federation
```

Подсистема используется в:

- `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/ingestion.py`
- `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/_connector_bridge.py`
- `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/executor.py`
- `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/explore_lane.py`
- `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/data_plane/modes.py`

## Архитектурные блоки

### 1) Контракты и capability-модель

- `base.py`: `SourceConnector`, `BaseConnector`, `ConnectionConfig`, `ConnectionHandle`.
- `capabilities.py`: capability decorators, runtime checks, protocol compliance.
- `types/`: унификация типов данных, units/dimensions/temporal/coercion и error-модель.

### 2) Реестр и lifecycle

- `registry.py` — публичный фасад.
- `registry_core.py`, `registry_core_parts.py`, `_registry_*` — реализация `ConnectorRegistry`.
- `discovery.py` — загрузка built-in, entry points и explicit модулей.
- `pool.py` — connection pooling.

### 3) Execution-слои вокруг fetch

- `cache/` — CAS-backed cache + TTL/LRU/smart policies + invalidation/prefetch/proxy.
- `resilience/` — retry, circuit breaker, rate limit, fallback, unified wrappers.
- `contracts/` — schema contracts, inference/evolution, validating middleware.
- `quality/` — freshness/completeness/consistency и формирование quality reports.
- `transform/` — конвейер преобразований табличных payload.
- `federation/` — planner/ranker/resolver/composer для объединения нескольких источников.

### 4) Профили и конфигурации

- `profiles/` — connection profiles (`SourceProfileRegistry`).
- `bindings/` — mapping/binding profiles для связки схемы и целевой структуры.

### 5) Реализации коннекторов

- `sources/` — production implementations (`WorldBank`, `Eurostat`, `UKONS`, `SDMX`, `CKAN`, `Socrata`, `Opendatasoft`, `SPARQL`, `REST`).
- `reference/` — reference adapters (`StaticCSV`, generic `REST`, `SDMX`).

### 6) Testing и record/replay интеграция

- `testing/` — harness, fixtures, simulator, fault-injection.
- `testing/simulator.py` используется `fabric.data_plane` в режимах `record`/`replay`.

## Как обычно вызывать

1. Через ingestion path: `run_connectors_ingestion(...)`.
2. Через bridge path: `fabric_get_data(...)`.
3. Для retrieval: `FetchExecutor.execute(...)` и `ExploreLaneDiscovery.discover(...)`.

Прямой вызов `connector.fetch(...)` допустим, но не является приоритетным сценарием для верхнего слоя.

## Связи

- `polisyos.ir.connectors` — канонические `FetchRequest/FetchResult`, capabilities и versioning.
- `polisyos.fabric.catalog` и `polisyos.fabric.retrieval` — выбор источников и построение fetch plans.
- `polisyos.fabric.evidence`/`provenance` — трассировка происхождения данных.
