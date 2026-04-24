# ADR 0021: Connector Schema Contracts and StoragePort Boundary

- Status: Accepted
- Date: 2026-02-08

## Context

Phase 16 requires:

1. A formal connector-to-schema contract with runtime validation and evolution checks.
2. Schema-aware cache invalidation to avoid serving stale payloads after schema changes.
3. Production connectors for World Bank, Eurostat, and UK ONS.
4. Removal of direct `scholar -> fabric.io.db.SimulationDB` dependency.

Before this ADR:

- `DataSchema` existed, but connector outputs were not bound to declared contracts.
- Cache metadata stored `schema_hash`, but no contract-driven invalidation trigger existed.
- Scholar imported `SimulationDB` directly, violating intended abstraction boundaries.

## Decision

### 1. Connector Contracts

- Introduce immutable `ConnectorSchemaContract` and `ContractRegistry`.
- Enforce schema evolution with `SchemaEvolution.compare()` during registration.
- Require semantic version bumps aligned with change severity.
- Provide `ContractValidatingProxy` for fetch-time schema and quality checks.

### 2. Cache Coherence

- Use `ConnectorSchemaContract.content_hash` as cache `schema_hash`.
- Add `ConnectorCacheStore.invalidate_by_schema_hash()`.
- Register `SchemaChangeInvalidationTrigger` as contract registry callback.

### 3. Production Connectors

- Add production source connectors:
  - `WorldBankConnector`
  - `EurostatConnector`
  - `UKONSConnector`
- Publish them via built-in discovery and `polisyos.connectors` entry points.

### 4. StoragePort

- Introduce `StoragePort` protocol under `fabric.storage`.
- Provide `DuckDBStorageAdapter` and `InMemoryStorageAdapter`.
- Add `transaction()` to the protocol for atomic multi-write workflows.
- Refactor Scholar to accept `storage: StoragePort | None`.
- Keep deprecated `db` shim in Scholar entrypoints for compatibility.

## Consequences

### Positive

- Downstream consumers get explicit, enforceable connector schema guarantees.
- Cache entries become schema-coherent across contract updates.
- Scholar becomes storage-backend agnostic and test-friendly.
- Backward compatibility is preserved during migration.

### Negative

- New connector implementations must maintain explicit contracts.
- Runtime validation adds overhead for large payloads.
- Non-DuckDB storage backends currently have reduced functionality for complex
  conflict-resolution SQL joins until richer storage query capabilities are added.

## Follow-up

- Add PostgreSQL adapter implementing `StoragePort`.
- Extend contract snapshots into ABI gate if contracts become first-class ABI artifacts.
- Gradually phase out Scholar `db` shim after migration window.
