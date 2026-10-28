# Connectors (`polisyos.fabric.connectors`)

`polisyos.fabric.connectors` is the protocol, registry, profile, cache,
contract, and resilience layer for fetching external data sources safely and
deterministically.

Last updated: 2026-10-22.

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
The supported facade exposes `SourceProfile` as an exact alias to the profile owner. A profile is configuration evidence, not verification of the configured source.


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

## Runtime state and HTTP responses

ConnectionHandle.get_state(), set_state(), and setdefault_state() remain
available for compatibility with connector extensions. Built-in connectors
use owner-specific typed state keys: a missing key can receive its documented
default, explicit None is retained only for nullable keys, and a present
value with the wrong shape raises instead of being silently replaced. The
existing per-handle lock makes typed setdefault atomic and validates both its
proposed value and any existing winner.

Shared HTTP readers consume response objects through read-only headers and
content properties. At the consumption boundary, the header get method must be
callable synchronously and return str or None for Content-Length; present
values are read from their native string contents and must contain only ASCII
decimal digits. Only an absent header is treated as missing, and an
over-limit declaration is refused before body consumption. The chunked reader
is adapted at the consumer boundary, then checks the returned async stream and
each yielded bytes chunk before size limits, classification, and progress
callbacks run. Stream chunks and the fallback read() result are normalized
from their native bytes contents before size checks, callbacks, scanning, or
return. Non-bytes chunks and fallback bodies are refused. The fallback
response.read() path still materializes the whole body before actual-size and
PII checks, and the chunked path appends a yielded chunk before checking its
cumulative size. These checks reject oversized results but do not cap
transient allocation; PII scanning runs on the whole consumed body rather than
concurrently with input.

Cached HTTP JSON and SDMX HEAD executors are held by nominal owner adapters.
Each adapter invokes the stored callable with the runtime arguments, verifies
that the result is awaitable, and checks the response tuple or header mapping
before returning it. The public raw-response observer remains a static, synchronous protocol;
runtime state stores an adapter that checks required calls at their real
invocation points while optional hooks remain optional. A callback returning an
awaitable is rejected before later work in that path; native coroutine results
are closed and Future results cancelled. An exposed close or cancel hook on a
custom awaitable is called synchronously. Native coroutine results from that
hook are closed before their body runs, and Future results are cancelled. Other
hook-returned awaitables are left unawaited rather than recursively traversed:
the Awaitable protocol has no general disposal operation, so cleanup of opaque
custom awaitables remains a bounded residual.

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
admission budget. Failed disconnect retains its cleanup owner; in-flight acquire
transitions keep their capacity reservation until physical cleanup succeeds.
`close_all()` retries retained owners and refuses to report a completed drain
until physical cleanup succeeds. Circuit/live journal permissions are independent
of this admission budget and do not establish external data authority.

## Resilience regulator ownership

A declared rate must be finite and positive; `None` means that this layer has
no configured rate limit. A mapping's explicitly supplied `rate_limit_rps`
takes precedence over its alias even when the value is zero, so invalid
configuration cannot silently opt out. Calls may raise
`BoundedResourceRegistryCapacityError` when the bounded protected-state budget
cannot admit a different key; retry only under an explicit higher-level policy.

Rate and circuit decorators keep a lease on the selected regulator through
the operation, and the internal registry evicts only unleased quiescent state.
Typed provider `RateLimitError` cooldown is recorded on that same limiter
before the error is propagated. Local capacity and invalid-rate refusals keep
their exception contracts and release the circuit attempt without recording a
provider failure; only the originating in-process owner marks such a refusal.
The same public exception type raised by a provider does not by itself claim
local origin.

REST page requests reuse a connector-owned wrapper across pages and fetches.
The general decorator's existing identity uses connector and endpoint, with
rates as separate configuration keys. Numerically equal rates use the same
key. These keys do not establish provider-global quota scope, tenant authority,
cross-instance, or cross-process sharing.

`with_rate_limit` accepts a numeric rate or a synchronous callable that
resolves the rate from each call's arguments; a callable may return `None` to
opt out for that call. Existing numeric calls remain valid. The internal
registry no longer returns unleased mutable regulators; consumers must hold its
lease for the complete use and must not retain the value after release.

## Registration and handle ownership

Registration selects a connector definition and factory separately from its
metadata ID. The registry captures their origin, the runtime owner ID, and a
registration generation. Lookup, ordinary and live-permit acquisition, and
stream creation use that same selection. A registration-time dependency-injection
factory remains supported. Replacing the public entry's factory, class, runtime
owner, admitted instance, or loaded flag does not admit a replacement producer;
use `register(..., override=True)` instead. `get_entry()` remains available for
runtime health and failure state, and `set_default_config()` sets the default
connection configuration.

An override selects a new generation pool for new acquisitions. Active handles
from the old generation keep their original pool and cleanup owner; a handle's
route tag only orders the search for its exact owner. After the last release,
an old generation pool may remain idle until shutdown or capacity trimming.
Registration and physical cleanup do not establish source custody, permission,
currentness, or the authority of the fetched data.

Freshness scans release each successfully acquired handle through the
registry, including when a connector freshness check raises. A release failure
is logged and does not establish that physical cleanup completed.

## Reference Docs

- [Fabric connectors reference](../../../../docs/reference/fabric/connectors.md)
- [Fabric profiles reference](../../../../docs/reference/fabric/profiles.md)
- [Connector CONTRIBUTING guide](../../../../docs/connectors/CONTRIBUTING.md)
- [Add data source](../../../../docs/how-to/add-data-source.md)
- [Manage generated artifacts](../../../../docs/how-to/manage-generated-artifacts.md)
- [Fabric tests map](../../../../tests/unit/fabric/README.md)
