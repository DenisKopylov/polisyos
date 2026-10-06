# Connectors (`polisyos.fabric.connectors`)

`polisyos.fabric.connectors` is the protocol, registry, profile, cache,
contract, and resilience layer for fetching external data sources safely and
deterministically.

Last updated: 2026-04-17.

## Purpose

Use this package when you need to define a connector family, register it,
attach schema contracts and source profiles, or debug runtime fetch behavior.
It owns the fetch surface that the rest of Fabric uses for ingestion,
retrieval, and streaming.

## Where to Start

- Read [__init__.py](./__init__.py) to see the exported connector facade.
- Read [base.py](./base.py), [registry.py](./registry.py), and
  [profiles/registry.py](./profiles/registry.py) for protocol, registry, and
  profile boundaries.

- Read [contracts/schema.py](./contracts/schema.py) and
  [transform/pipeline.py](./transform/pipeline.py) for schema evolution and
  transform correctness rules.

- Read [testing/harness.py](./testing/harness.py) and
  [tests/unit/fabric/connectors](../../../../tests/unit/fabric/connectors) before adding
  a new family or changing shared behavior.

- Read [Connector CONTRIBUTING](../../../../docs/connectors/CONTRIBUTING.md)
  and [Add data source](../../../../docs/how-to/add-data-source.md) for the
  current contributor workflow.

## Public Entrypoints

| Entrypoint                                                     | Description                                                                        |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `SourceConnector` / `BaseConnector`                            | Core fetch protocol and shared implementation base.                                |
| `FetchRequest` / `FetchResult`                                 | Public request and result models.                                                  |
| `ConnectorRegistry`                                            | Runtime registration, lookup, and lifecycle management.                            |
| `discover_connectors()`                                        | Built-in and entry-point discovery helper.                                         |
| `SourceProfile` / `SourceExecutionPolicy`                      | Planner/runtime configuration boundary for source behavior.                        |
| `resolve_connection_config()` / `resolve_execution_policy()`   | Turn profiles into runtime-safe connector settings.                                |
| `validate_protocol_compliance()`                               | Executable capability and method-contract validation.                              |
| `ConnectorCacheStore`, resilience helpers, contract registries | Shared runtime layers for cache, retry, fallback, schema, and governance behavior. |

## Depends On / Depended On By

- Depends on: `polisyos.ir.connectors`, `polisyos.core.components`, and the
  connector subpackages for contracts, profiles, cache, resilience, and
  testing.

- Depended on by: `polisyos.fabric.ingestion`, `polisyos.fabric.retrieval`,
  `polisyos.fabric.data_plane.streaming`, `polisyos.runtime.http.services.control`,
  and `polisyos.data_forge.domains.catalog.batch.core_sources_ingest`.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg -n "SourceConnector|BaseConnector|ConnectorRegistry|SourceProfile" src/polisyos/fabric/connectors`
  Jump to the protocol, registry, and profile surfaces. Smoke-tested on
  2026-04-17.

- `rg --files src/polisyos/fabric/connectors/sources | sort`
  Inspect the concrete connector implementations shipped in this workspace.
  Smoke-tested on 2026-04-17.

- `rg -n "polisyos\\.fabric_connectors" pyproject.toml`
  Check the current connector entry-point registrations. Smoke-tested on
  2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/connectors/test_registry.py tests/unit/fabric/connectors/test_protocol_compliance.py -q`
  Registry and protocol smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/connectors/test_contract_system.py tests/unit/fabric/connectors/test_schema_system.py -q`
  Contract and schema-governance smoke suite. Smoke-tested on 2026-04-17.

- `uv run polisyos-tools connectors check-contracts --check`
  Connector contract snapshot gate. Conceptual in this README refresh: the
  current workspace reports stale snapshot drift and suggests `--update`.

- `uv run pytest tests/unit/fabric/connectors -q`
  Full connector suite. Conceptual in this README refresh; not run in this
  pass.

## Reference Docs

- [Fabric connectors reference](../../../../docs/reference/fabric/connectors.md)
- [Fabric profiles reference](../../../../docs/reference/fabric/profiles.md)
- [Connector CONTRIBUTING guide](../../../../docs/connectors/CONTRIBUTING.md)
- [Add data source](../../../../docs/how-to/add-data-source.md)
- [Manage generated artifacts](../../../../docs/how-to/manage-generated-artifacts.md)
- [Fabric tests map](../../../../tests/unit/fabric/README.md)

## Acquisition ownership

`PoolConfig.acquire_timeout_seconds` is one monotonic admission budget through
semaphore wait, connection creation, validation, and the final metadata commit.
A connector that suppresses cancellation can finish physical work late; the pool
owns and disconnects its handle before releasing its capacity reservation and
refuses admission after expiry or a newly observed caller cancellation. The task's
cancellation count at entry distinguishes an earlier handled cancellation from a
new cancellation of this acquisition. Successful publication retires the acquisition
registration under the same lock, with no later await before returning the handle.

Cleanup remains cooperative: an unresponsive physical disconnect can outlive the
admission budget. Failed disconnect retains the cleanup owner and its permit;
`close_all()` retries that owner and refuses to report a completed drain until
physical cleanup succeeds. Circuit/live journal permissions are independent of
this admission budget and do not establish external data authority.

## Resilience operation ownership

Rate-limit and circuit decorators lease the same keyed regulator for the complete
provider operation. Registry TTL/LRU may remove an entry only when its regulator is
neutral and no operation owns it. A refilled token bucket remains owned while its
provider awaits; later Retry-After feedback applies to the original keyed regulator.
Protected capacity is finite and refuses a new owner before provider work starts.
Same-key concurrent owners share the regulator, and cancellation/error releases
only that operation's lease. State-based `get_or_create` remains a lookup API;
operation consumers use `lease` across their awaited work.
