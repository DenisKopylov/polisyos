# Data Fabric Connectors

**Phase 2.1+: Расширенная система коннекторов**
**Phase 2.1: Protocol Foundation & Capability System**
**Phase 2.2: Registry Architecture & Lazy Loading**
**Phase 2.3+: Federation, Quality, Resilience & Advanced Features**

This package provides comprehensive abstractions for connecting to external
sources in the PolicyOS data fabric layer. The connector system uses a
**Protocol-based design** for structural subtyping, allowing connectors to be
implemented without inheriting a base class, with advanced features for
federation, caching, quality assurance, and resilience.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         IR Layer                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ connectors.py                                                ││
│  │ • ConnectorCapability (Flag Enum)                           ││
│  │ • TrustLevel, QualityTier (IntEnums)                        ││
│  │ • DataVersion, ConnectorMetadataSpec (Pydantic Models)       ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Fabric Layer                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ fabric/connectors/                                          ││
│  │ ├── base.py         # SourceConnector Protocol              ││
│  │ │   • FetchRequest (frozen dataclass)                       ││
│  │ │   • FetchResult[DataT] (Generic Pydantic model)           ││
│  │ │   • ConnectionConfig/Handle                               ││
│  │ ├── capabilities.py # Validation utilities                  ││
│  │ │   • @requires_capability decorator                        ││
│  │ │   • validate_protocol_compliance()                        ││
│  │ ├── types.py        # Extended error hierarchy & types      ││
│  │ │   • ConnectorError, CapabilityError, etc.                 ││
│  │ │   • DatasetDescriptor, FreshnessResult                    ││
│  │ │   • Coercion, dimensions, temporal, units                 ││
│  │ ├── registry.py     # ConnectorRegistry singleton           ││
│  │ │   • Lazy loading + instance caching                        ││
│  │ │   • Secondary indices for capability queries              ││
│  │ ├── pool.py         # ConnectionPool + lifecycle mgmt        ││
│  │ │   • Health checks, eviction, concurrency limits           ││
│  │ ├── discovery.py    # Plugin discovery via entry points      ││
│  │ │   • Dev-only path discovery gated by env flag             ││
│  │ ├── cache/          # CAS-based caching system              ││
│  │ │   ├── store.py    # Content Addressable Storage           ││
│  │ │   ├── policy.py   # Caching policies & invalidation       ││
│  │ │   └── proxy.py    # Proxy layer for caching               ││
│  │ ├── contracts/      # Contract evolution & schema inference ││
│  │ │   ├── evolution.py # Contract versioning                  ││
│  │ │   ├── inference.py # Automatic schema inference           ││
│  │ │   └── registry.py # Contract registry                     ││
│  │ ├── federation/     # Federated query composition           ││
│  │ │   ├── composer.py # Query composition across sources      ││
│  │ │   ├── planner.py  # Federated query planning              ││
│  │ │   └── resolver.py # Dependency resolution                 ││
│  │ ├── quality/        # Data quality assessment                ││
│  │ │   ├── completeness.py # Completeness validation           ││
│  │ │   ├── freshness.py # Data freshness checks                ││
│  │ │   └── validator.py # Quality validation pipeline          ││
│  │ ├── resilience/     # Fault tolerance patterns              ││
│  │ │   ├── circuit_breaker.py # Circuit breaker pattern        ││
│  │ │   ├── fallback.py # Fallback mechanisms                   ││
│  │ │   └── retry.py    # Retry strategies                      ││
│  │ ├── testing/        # Testing harness & simulation          ││
│  │ │   ├── harness.py  # Test harness for connectors           ││
│  │ │   └── simulator.py # Connector simulation                 ││
│  │ ├── transform/      # Data transformation pipeline          ││
│  │ │   ├── __init__.py  # Transform API                         ││
│  │ │   ├── aggregator.py # Data aggregation                     ││
│  │ │   ├── filter.py    # Data filtering                        ││
│  │ │   ├── harmonizer.py # Schema harmonization                 ││
│  │ │   ├── imputer.py   # Missing value imputation              ││
│  │ │   ├── normalizer.py # Data normalization                   ││
│  │ │   ├── pipeline.py  # Transformation pipeline               ││
│  │ │   └── validator.py # Transformation validation             ││
│  │ └── __init__.py     # Public API                            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### SourceConnector Protocol

```python
from polisyos.fabric.connectors import (
    SourceConnector,
    FetchRequest,
    FetchResult,
    ConnectorCapability,
    ConnectionConfig,
    ConnectionHandle,
)

class MyConnector(SourceConnector[list[dict]]):
    connector_id: ClassVar[str] = "myorg.mydata"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH | ConnectorCapability.CATALOG_BROWSE
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(...)

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        ...

    async def disconnect(self, handle: ConnectionHandle) -> None:
        ...

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        ...

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict]]:
        ...
```

### Capability System

```python
from polisyos.ir.connectors import ConnectorCapability, capabilities_from_flags

caps = (
    ConnectorCapability.FULL_FETCH |
    ConnectorCapability.STREAMING |
    ConnectorCapability.DATE_RANGE_FILTER
)
```

### FetchRequest and CAS Keys

`FetchRequest` provides two deterministic hashes:

- `query_key` identifies the logical data request (pagination excluded)
- `request_key` includes pagination and output preferences
- `cache_key` is an alias for `request_key`

Filters are canonicalized as an order-insensitive mapping for stable keys.

```python
from polisyos.fabric.connectors import FetchRequest
from datetime import datetime, timezone

request = FetchRequest(
    dataset_id="worldbank.wdi.GDP.MKTP.CD",
    date_start=datetime(2020, 1, 1, tzinfo=timezone.utc),
    date_end=datetime(2023, 12, 31, tzinfo=timezone.utc),
    filters=(
        ("country", ("USA", "DEU", "FRA")),
        ("indicator", ("GDP.MKTP.CD",)),
    ),
)

print(request.query_key)
print(request.request_key)
```

Execution hints:

- `FetchRequest.retryable=False` disables automatic retries for non-idempotent operations.

### Protocol Compliance Validation

```python
from polisyos.fabric.connectors import validate_protocol_compliance

violations = validate_protocol_compliance(MyConnector)
if violations:
    raise ConfigurationError(f"Protocol violations: {violations}")
```

### Advanced Components (Phase 2.3+)

#### Caching System (`cache/`)
CAS-based кэширование с политиками инвалидации и prefetch для оптимизации производительности:
```python
from polisyos.fabric.connectors.cache import CacheStore, CachePolicy

cache = CacheStore()
policy = CachePolicy(ttl_hours=24, max_size_mb=100)
```

#### Federation (`federation/`)
Композиция запросов к множественным источникам данных с dependency resolution:
```python
from polisyos.fabric.connectors.federation import QueryComposer, FederatedPlanner

composer = QueryComposer()
plan = composer.compose([source1, source2, source3])
```

#### Quality Assessment (`quality/`)
Оценка качества данных коннекторов (completeness, consistency, freshness):
```python
from polisyos.fabric.connectors.quality import QualityValidator

validator = QualityValidator()
report = validator.validate(dataset, QualityThresholds())
```

#### Resilience Patterns (`resilience/`)
Fault tolerance с circuit breaker, fallback и retry механизмами:
```python
from polisyos.fabric.connectors.resilience import CircuitBreaker, RetryStrategy

breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
retry = RetryStrategy(max_attempts=3, backoff=ExponentialBackoff())
```

#### Data Transformation (`transform/`)
Комплексный pipeline трансформаций данных с поддержкой всех этапов ETL:

```python
from polisyos.fabric.connectors.transform import (
    TransformationPipeline, Aggregator, Filter, Harmonizer,
    Imputer, Normalizer, Validator
)

# Создание полного transformation pipeline
pipeline = TransformationPipeline([
    Filter(column='status', operator='!=', value='invalid'),  # Фильтрация
    Harmonizer(target_schema=standard_schema),                # Гармонизация схемы
    Imputer(strategy='mean', columns=['price', 'volume']),    # Заполнение пропусков
    Normalizer(method='zscore', columns=['price']),           # Нормализация
    Aggregator(group_by=['date'], operations={'volume': 'sum'}), # Агрегация
    Validator(rules=[not_null_rule, range_rule])              # Валидация
])

# Применение к данным
transformed_data = pipeline.apply(raw_data)
```

### Connector Registry (Phase 2.2)

```python
from polisyos.fabric.connectors import ConnectorRegistry, ConnectorCapability

registry = ConnectorRegistry.get_instance()

# Register and lazily instantiate
registry.register(MyConnector)
connector = registry.get("myorg.mydata")

# Query by capability
streaming = list(registry.query(capabilities=ConnectorCapability.STREAMING))
```

### Connection Pooling (Phase 2.2)

```python
from polisyos.fabric.connectors import PoolConfig

handle = await registry.get_connection("myorg.mydata")
await registry.release_connection("myorg.mydata", handle)

stats = registry.stats
print(stats.active_pools)
```

Pools are keyed by `(connector_fqid, config_fingerprint)` to prevent credential
mixing across tenants or base URLs.

### Discovery (Phase 2.2)

Entry points can be registered in `pyproject.toml`:

```toml
[project.entry-points."polisyos.connectors"]
world_bank = "mypackage.connectors:WorldBankConnector"
```

Filesystem path discovery is **dev-only** and gated by `POLISYOS_ALLOW_CONNECTOR_PATHS=1`.

## Capability Reference

| Capability | Description | Required Method |
|------------|-------------|-----------------|
| `CATALOG_BROWSE` | List available datasets | `list_datasets` |
| `FULL_FETCH` | Fetch entire dataset | `fetch` |
| `INCREMENTAL_FETCH` | Fetch changes since timestamp | `fetch` |
| `STREAMING` | Stream large datasets | `fetch_stream` |
| `DATE_RANGE_FILTER` | Server-side date filtering | - |
| `DIMENSION_FILTER` | Server-side dimension filtering | - |
| `CUSTOM_QUERY` | Query language support | - |
| `SCHEMA_INTROSPECTION` | Describe data schema | `get_dataset_schema` |
| `FRESHNESS_CHECK` | Check staleness | `check_freshness` |
| `PROVENANCE_METADATA` | Source/methodology info | - |
| `REVISION_HISTORY` | Historical revisions | - |
| `CONFIDENCE_INTERVALS` | Uncertainty bounds | - |
| `RATE_LIMIT_AWARE` | Report rate limit status | - |
| `RESUMABLE` | Resume interrupted fetches | - |

## Error Hierarchy

```
ConnectorError (base)
├── CapabilityError      # Missing required capability
├── ConfigurationError   # Invalid configuration
├── ConnectionError      # Connection failures
│   └── RateLimitError   # Rate limit exceeded
├── FetchError           # Fetch operation failed
└── SchemaError          # Schema validation failed
```

## Architectural Constraints

- **Law A (Dependency Direction)**: May import from `polisyos.ir`, `polisyos.core`
- **Law D (Deterministic Caching)**: `FetchRequest` hashes use canonical JSON
- **Law E (Evidence Tracking)**: `FetchResult.evidence_ref` links to evidence bundles

## Testing

```bash
pytest tests/fabric/connectors/test_protocol_compliance.py -v
```

## Future Phases

- Phase 2.3: Schema Contracts and Inference
- Phase 2.4: Caching Layer with CAS Integration
- Phase 2.8: Federation and Multi-source Composition
