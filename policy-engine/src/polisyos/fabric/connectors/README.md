# Data Fabric Connectors

**Phase 2.1: Protocol Foundation & Capability System**

This package provides the foundational abstractions for connecting to external
sources in the PolicyOS data fabric layer. The connector system uses a
**Protocol-based design** for structural subtyping, allowing connectors to be
implemented without inheriting a base class.

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
│  │ ├── types.py        # Error hierarchy & supporting types    ││
│  │ │   • ConnectorError, CapabilityError, etc.                 ││
│  │ │   • DatasetDescriptor, FreshnessResult                    ││
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

### Protocol Compliance Validation

```python
from polisyos.fabric.connectors import validate_protocol_compliance

violations = validate_protocol_compliance(MyConnector)
if violations:
    raise ConfigurationError(f"Protocol violations: {violations}")
```

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

- Phase 2.2: Registry and Discovery System
- Phase 2.3: Schema Contracts and Inference
- Phase 2.4: Caching Layer with CAS Integration
- Phase 2.5: Federation and Multi-source Queries
