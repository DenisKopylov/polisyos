# Connectors

`polisyos.fabric.connectors` — подсистема подключения внешних источников и исполнения `fetch` с окружением надежности, валидации и композиции данных.

## Роль в Fabric

```text
ConnectorRegistry
  -> SourceConnector.fetch/list_datasets/fetch_stream
  -> FetchResult
  -> (cache/resilience/contracts/quality/transform/federation)
```

Основные потребители:

- [ingestion.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/ingestion.py)
- [_connector_bridge.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/_connector_bridge.py)
- [retrieval/executor.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/executor.py)
- [retrieval/explore_lane.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/explore_lane.py)
- [data_plane/modes.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/data_plane/modes.py)

## Архитектура

- `base.py`, `capabilities.py`, `types/` — protocol `SourceConnector`, capability checks, unified connector types/coercion/units/temporal.
- `registry.py` + `registry_core*.py` + `_registry_*` — runtime registry и lifecycle.
- `discovery.py` — discovery built-in modules, entry points и explicit modules/paths (dev-gated).
- `pool.py` — connection pooling.
- `profiles/` и `bindings/` — singleton registries reusable профилей подключения и binding-профилей.
- `contracts/` — schema contracts, inference, evolution и validation middleware.
- `cache/` — CAS-backed cache store, policies, invalidation, prefetch, proxy.
- `resilience/` — retry, circuit breaker, rate limiting, fallback wrappers.
- `quality/` — freshness/completeness/consistency, quality reports.
- `transform/` — tabular pipeline (normalizer/filter/imputer/aggregator/validator).
- `federation/` — planner/ranker/resolver/composer для multi-source composition + audit merge logs.
- `components.py` и `components_bridge.py` — интеграция коннекторов в `polisyos.core.components`.

## Текущие production connectors (`sources/`)

- `WorldBankConnector`
- `WVSConnector`
- `EurostatConnector`
- `UKONSConnector`
- `SDMXSourceConnector`
- `CKANCatalogConnector`
- `CKANResourceConnector`
- `SocrataConnector`
- `OpendatasoftConnector`
- `RestJsonConnector`
- `SPARQLConnector`

Reference adapters (для шаблонных интеграций) находятся в `reference/`.

## Execution-paths

- Ingestion path: `run_connectors_ingestion(...)`.
- Bridge path: `fabric_get_data(...)`.
- Retrieval path: `FetchExecutor.execute(...)`, `ExploreLaneDiscovery.discover(...)`.
- Streaming path: `fetch_stream(...)` используется `data_plane.run_streaming_windowed(...)`.

## Тестирование и replay

- `testing/simulator.py` (`APISimulator`) — HTTP record/replay.
- Интегрировано с `fabric.data_plane` режимами `record` и `replay`.

## Связи

- `polisyos.ir.connectors` — канонические `FetchRequest/FetchResult`, capabilities, metadata.
- `fabric.catalog` + `fabric.retrieval` — планирование и разрешение источников.
- `fabric.evidence` / `fabric.provenance` — provenance/evidence след данных.
