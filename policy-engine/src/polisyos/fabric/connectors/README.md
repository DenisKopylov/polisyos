# Connectors — External Data Source System

Protocol-based система подключения к внешним источникам данных с capability-driven security, кэшированием, resilience и federation.

## Архитектура

```
IR Layer (polisyos.ir.connectors)
  ConnectorCapability, FetchRequest/FetchResult, DataVersion, QualityTier, TrustLevel
        │
        ▼
Fabric Layer (polisyos.fabric.connectors)
  ├── base.py          SourceConnector Protocol, ConnectionConfig/Handle
  ├── capabilities.py  @requires_capability, validate_protocol_compliance()
  ├── types.py         Error hierarchy, DatasetDescriptor, ValidationResult
  ├── sources/         Production connectors + shared HTTP runtime (`http_base.py`, `http_common.py`)
  ├── registry.py      ConnectorRegistry singleton (lazy loading, secondary indices)
  ├── pool.py          ConnectionPool (health checks, eviction, concurrency)
  ├── discovery.py     Plugin discovery via entry points
  ├── validation.py    Schema coercion/validation для FetchResult
  ├── cache/           CAS-based caching (7 файлов)
  ├── resilience/      Circuit breaker, retry, rate limiter, fallback (5 файлов)
  ├── federation/      Cross-connector query composition (7 файлов)
  ├── quality/         Data quality validators (6 файлов)
  ├── contracts/       Schema evolution и contract registry (4 файла)
  ├── reference/       Эталонные реализации: REST JSON, SDMX, CSV (4 файла)
  ├── testing/         Test harness, fixtures, simulator (5 файлов)
  ├── transform/       DAG-based transformation pipeline (8 файлов)
  └── types/           Type system: coercion, dimensions, temporal, units (6 файлов)
```

## SourceConnector Protocol

Structural subtyping — коннектор не обязан наследовать base class:

```python
@runtime_checkable
class SourceConnector(Protocol[DataT]):
    connector_id: ClassVar[str]
    capabilities: ClassVar[ConnectorCapability]
    metadata: ClassVar[ConnectorMetadataSpec]

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle: ...
    async def disconnect(self, handle: ConnectionHandle) -> None: ...
    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[DataT]: ...
    async def health_check(self, handle: ConnectionHandle) -> HealthStatus: ...
```

Опциональные методы (capability-gated): `list_datasets()`, `stream_fetch()`, `check_freshness()`, `validate_data()`.

`BaseConnector` — convenience base class с default реализациями.

## ConnectorRegistry

Singleton с lazy loading и capability-based queries:

```python
registry = ConnectorRegistry.get_instance()
registry.register(connector, config=default_config)
connector = registry.get("world_bank")
entries = registry.query_entries(capabilities=ConnectorCapability.DATE_RANGE_FILTER)
```

**Connection lifecycle:** `get_connection()` → use → `release_connection()`. Pool автоматически управляет health checks и eviction.

## Подсистемы

### Cache (`cache/`)

CAS-based кэширование с pluggable политиками:

| Политика | Назначение |
|----------|-----------|
| `TTLPolicy` | Time-to-live expiration |
| `StaticDataPolicy` | Для неизменяемых данных |
| `VolatileDataPolicy` | Для быстро меняющихся данных |
| `SmartExpiryPolicy` | Адаптивная на основе паттернов |
| `LRUPolicy` | Least Recently Used eviction |
| `SizeBoundedPolicy` | Ограничение по размеру |

`CachingConnectorProxy` оборачивает коннектор, `InvalidationOrchestrator` управляет инвалидацией, `PrefetchScheduler` — предзагрузкой.

### Resilience (`resilience/`)

Паттерны отказоустойчивости:

- **`CircuitBreaker`** — open/half-open/closed, configurable thresholds
- **`RetryPolicy`** — exponential backoff, jitter, retryable error classification
- **`RateLimiter`** / `AdaptiveRateLimiter` — token bucket, adaptive adjustments
- **`FallbackStrategy`** — `CacheFallback`, `MockFallback`, `RaiseFallback`, `FallbackChain`

Composable через `apply_resilience(config)` или отдельные декораторы `with_retry`, `with_circuit_breaker`, `with_rate_limit`, `with_fallback`.

### Federation (`federation/`)

Cross-connector запросы и агрегация:

- **`planner.py`** — query plan: какие коннекторы нужны, в каком порядке
- **`composer.py`** — composition: сборка результатов из нескольких коннекторов
- **`resolver.py`** — dependency resolution между коннекторами
- **`ranker.py`** — ранжирование коннекторов по quality/trust
- **`evidence_aggregation.py`** — composite evidence bundles из нескольких источников

### Quality (`quality/`)

Валидация данных после fetch:

- **`completeness.py`** — проверка полноты (null ratio, expected fields)
- **`consistency.py`** — проверка консистентности (referential integrity, ranges)
- **`freshness.py`** — проверка актуальности (data age, cache age)
- **`validator.py`** — `DataQualityValidator` orchestrator
- **`report.py`** — `DataQualityReport` → конвертируется в `QualityIndicators`

### Transform (`transform/`)

Composable DAG-based pipeline для трансформации данных после fetch:

```python
pipeline = (
    TransformPipeline()
    .normalize(field_mappings={"GDP": "gdp_usd"})
    .harmonize_codes("country", "ISO_3166_ALPHA3")
    .aggregate(by=["country", "year"], aggregations={"gdp_usd": "sum"},
               temporal_context={"gdp_usd": TemporalType.FLOW})
    .impute_missing(strategy="linear")
    .validate(rules=[CompletenessRule("gdp_usd", threshold=0.95)])
)
result = pipeline.apply(data)
```

Stock/flow-safe агрегация: additive (flows можно суммировать по времени), semi-additive (stocks — только по entities), non-additive (rates, indices — нельзя суммировать). DAG branching и joining. Lineage tracking для каждого шага.

### Contracts (`contracts/`)

Schema evolution и управление контрактами коннекторов: schema inference из данных, evolution tracking (backward/forward compatibility), contract registry для API stability.

### Types (`types/`)

Система типов для данных коннекторов: type coercion, dimensional handling, temporal types, unit conversion.

### Reference (`reference/`)

Эталонные реализации коннекторов: `RestJsonConnector`, `SdmxConnector`, `StaticCsvConnector`.

### Testing (`testing/`)

Инфраструктура для тестирования коннекторов: `ConnectorTestHarness`, fixtures, `ConnectorSimulator`.

## Capability System

15+ capabilities как Flag Enum: `FULL_FETCH`, `STREAMING`, `DATE_RANGE_FILTER`, `CATALOG_BROWSE`, `SCHEMA_INTROSPECT`, `FRESHNESS_CHECK`, `DATA_VALIDATION`, etc.

`@requires_capability` — decorator для capability-gated методов.
`validate_protocol_compliance()` — проверка всех required methods/attributes.

## Error Hierarchy

```
ConnectorError
├── CapabilityError      # Capability not supported
├── ConfigurationError   # Invalid config
├── ConnectionError      # Connection failed
├── FetchError           # Fetch failed
├── RateLimitError       # Rate limit exceeded
└── SchemaError          # Schema mismatch
```

## Связи

- **IR** (`polisyos.ir.connectors`) — контракты: ConnectorCapability, FetchRequest/FetchResult, DataVersion
- **fabric/ingestion.py** — `run_connectors_ingestion()` использует registry + cache + transform
- **fabric/_connector_bridge.py** — `fabric_get_data()` — публичная точка для Scientist
- **fabric/evidence.py** — `build_composite_evidence_bundle()` делегирует в federation
