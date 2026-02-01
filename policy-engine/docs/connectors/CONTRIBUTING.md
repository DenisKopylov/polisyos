# Contributing a Data Connector to Policy OS

This guide walks you through every step required to add a new data
connector to the Policy OS Connector system. By the time you finish,
your connector will be protocol-compliant, lint-clean, and covered by
the shared test harness.

---

## Prerequisites

- Python 3.11+
- The Policy OS repository checked out and dependencies installed (`pip install -e ".[dev]"`)
- Familiarity with the SourceConnector protocol (see `src/polisyos/fabric/connectors/base.py`)

---

## Step 1 - Generate the Skeleton

Use the scaffold CLI to generate a compliant starting point:

```bash
python tools/connectors/scaffold.py create --name "MyDataSource" --type REST
```

**`--type` options:**

| Type | Capabilities generated | Use when... |
|---|---|---|
| `REST` | FULL_FETCH, DATE_RANGE_FILTER, RATE_LIMIT_AWARE | Your source is an HTTP/REST API |
| `CSV` | FULL_FETCH, SCHEMA_INTROSPECTION | Your source is a static or periodically-updated CSV file |
| `SQL` | FULL_FETCH, DATE_RANGE_FILTER, SCHEMA_INTROSPECTION | Your source is a relational database |
| `SDMX` | FULL_FETCH, CATALOG_BROWSE, STREAMING, FRESHNESS_CHECK | Your source is an SDMX-compliant statistical agency (IMF, Eurostat, OECD) |

This creates two files:

```
src/polisyos/fabric/connectors/sources/my_data_source.py   <- connector class
tests/fabric/connectors/sources/test_my_data_source.py     <- harness tests
```

---

## Step 2 - Implement the Connector

Open your generated source file and fill in every `TODO` section.
The minimum you must implement:

### 2a. `connect()` and `disconnect()`

Establish and tear down the connection to your data source. For REST APIs this typically means
creating an `httpx.AsyncClient` session. For databases, acquire a connection from a pool.

### 2b. `health_check()`

Perform a lightweight probe (e.g., a `HEAD` request or a `SELECT 1`).
Return `HealthStatus(healthy=True)` on success.

### 2c. `fetch()`

This is the core method. It must:

1. Translate the `FetchRequest` fields (`dataset_id`, `filters`, `date_start`, `date_end`) into
   the upstream API's query format.
2. Execute the query.
3. Return a `FetchResult` with:
   - `data` - the raw payload (`list[dict]`, `pandas.DataFrame`, or `pyarrow.Table`).
   - `row_count` - accurate count of returned rows.
   - `schema_id` / `schema_version` - referencing your connector's schema.
   - `version` - a `DataVersion` that uniquely identifies this snapshot of data.
   - `completeness` - a float in `[0.0, 1.0]` indicating data coverage.

### 2d. `validate_config()`

Check that the `ConnectionConfig` contains everything your connector needs (URL, API key, etc.)
at registration time. Return `ValidationResult.success()` or a result with issues.

---

## Step 3 - Run the Linter

Before committing, verify your connector respects the architectural Laws:

```bash
python tools/lint_connectors.py
```

This checks that your code does **not** import from:

| Forbidden prefix | Law | Why |
|---|---|---|
| `polisyos.scientist.*` | **Law A - Import Gate** | Connectors live in Fabric. Importing the orchestration layer creates a reverse dependency that breaks the directed acyclic dependency graph. |
| `polisyos.foundry.*` | **Law B - Foundry Purity** | Foundry is a pure JAX kernel with no I/O. Pulling it into a connector would violate that isolation. |

**If you need a type for type hints only**, guard the import:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.scientist.orchestrator import SomeType  # OK - warning only
```

---

## Step 4 - Run the Test Harness

Your generated test class inherits from `ConnectorTestHarness`, which automatically runs:

- **Protocol compliance** - verifies all required class attributes and async methods exist.
- **Lifecycle** - `connect()` -> `health_check()` -> `fetch()` -> `disconnect()`.
- **FetchResult validation** - ensures the result conforms to the contract.
- **Capability consistency** - checks that methods required by your declared capabilities are implemented.

```bash
pytest tests/fabric/connectors/sources/test_my_data_source.py -v
```

Add source-specific tests (e.g., pagination, error handling, rate limiting) in the
`TestMyDataSourceSpecific` class.

---

## Step 5 - Register the Connector

Add your connector to the registry. The canonical location is
`src/polisyos/fabric/connectors/sources/__init__.py`:

```python
from polisyos.fabric.connectors.sources.my_data_source import MyDataSourceConnector

from polisyos.fabric.connectors.registry import ConnectorRegistry

ConnectorRegistry.get_instance().register(
    connector_id="myorg.my_data_source",
    factory=MyDataSourceConnector,
    default_config=ConnectionConfig(
        url="https://api.example.com/v1/data",
    ),
)
```

---

## Step 6 - CI Validation

CI runs two checks automatically on every PR that touches
`src/polisyos/fabric/connectors/`:

1. **`lint_connectors.py`** - fails the build if any Law A/B violations are found.
2. **`pytest tests/fabric/connectors/`** - runs the full harness suite.

Both must pass before merge.

---

## Architectural Laws Quick Reference

| Law | Name | Connector Impact |
|---|---|---|
| **A** | Import Gate | You must not import `scientist.*` or `foundry.*` at runtime. |
| **B** | Foundry Purity | You must not import `foundry.*` at all (even for types, unless guarded). |
| **C** | Contracts as Truth | Use `FetchRequest` and `FetchResult` - do not invent ad-hoc wire types. |
| **D** | Auditability | Your `FetchResult` must include a `DataVersion`. The registry handles provenance graph construction. |
| **E** | Evidence Mandatory | The ingestion pipeline wraps your result in an `EvidenceBundle`. You do not need to do this yourself. |

---

## FAQ

**Q: Can my connector import `pandas`?**
A: Yes. `pandas` is a Fabric-layer dependency. The restriction is on `scientist` and
`foundry`, not on data-processing libraries.

**Q: My connector needs to call another connector for enrichment.**
A: Use the Federation layer (`fabric.connectors.federation`). Do *not* import a sibling
connector directly - route through the `ConnectorRegistry`.

**Q: How do I handle rate limits?**
A: Declare `ConnectorCapability.RATE_LIMIT_AWARE` and set `rate_limit_rps` on your
`ConnectionConfig`. The Resilience layer handles throttling automatically.

**Q: What if my data source is offline during CI?**
A: Use the `APISimulator` from the testing infrastructure in `REPLAY` mode. Record a
fixture once, replay it in CI. See `tests/fabric/connectors/test_harness.py` for examples.
