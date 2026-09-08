# Retrieval (`polisyos.fabric.retrieval`)

`polisyos.fabric.retrieval` turns a `DataNeed` into deterministic resolution,
bounded live discovery, executable fetch plans, previews, and promotion
signals.

## Persisted fetch custody

`execute_fetch_plans(..., persist_payload=True)` requires a real
`DatasetCatalogGraph` and CAS. The actual chosen plan, including a fallback,
must resolve through that graph. The executor persists the complete connector
payload and a `polisyos.fabric.fetch_receipt.v1` receipt; `DataContextMetric`
carries their typed `payload_ref` and `fetch_receipt_ref`. Its `sample_rows`
remain a preview and cannot substitute for the persisted payload.

`custody.resolve_persisted_fetch` resolves the full CAS chain, rechecks the
catalog source bytes, and repeats the exact full request through the registered
connector. A changed or unavailable source refuses current verification.
The comparison establishes current returned-content agreement. It does not
prove that the historical request happened at its recorded time, nor establish
scientific source truth. Capture timing stays in the raw receipt and cannot
authorize a time-sensitive or execution-cost claim.

Current N9 measurement admission uses
`MeasurementRootProducer.produce_from_fabric_fetch` with an explicit design
problem and a source requirement derived through the existing catalog owner.
Both existing connector and source-contract admission gates still apply.
The registry's full result validator checks the actual configured contract,
including schema, completeness, row counts and staleness. The root binds that
contract's ID, version and behavioral content hash; the current N9 reader
rechecks the same predicate and refuses a changed contract. Description and
creation metadata are outside that existing behavioral hash.
Each successful source recheck creates a fresh verification event, with its
own UTC `source_agreement_checked_at` and immutable authority identity. It
retains the original fetch reference without rewriting its capture time.
Catalog-only roots remain historical/fixture inputs and cannot discharge the
current MEASUREMENT obligation.

Last updated: 2026-04-17.

## Purpose

Use this package when you need the bridge between catalog knowledge and actual
fetch execution. Retrieval owns the fast-lane catalog resolution path, the
bounded explore lane, and the execution surfaces that turn candidates into
connector-backed results.

## Where to Start

- Read [__init__.py](./__init__.py) to see the exported retrieval surface.
- Read [service.py](./service.py) for the top-level orchestration and bounded
  local-index state.

- Read [executor.py](./executor.py) and [explore_lane.py](./explore_lane.py)
  for fetch execution and live discovery behavior.

- Read [../catalog/README.md](../catalog/README.md) and
  [../connectors/README.md](../connectors/README.md) for the upstream contract
  and source-binding surfaces that retrieval composes.

## Public Entrypoints

| Entrypoint                                             | Description                                                                 |
| ------------------------------------------------------ | --------------------------------------------------------------------------- |
| `RetrievalService`                                     | Main resolve, discover, and execute service.                                |
| `FetchExecutor`                                        | Executes fetch plans with preview/full gating.                              |
| `ExploreLaneDiscovery` / `ExploreLaneLimits`           | Bounded live discovery helper and its runtime limits.                       |
| `ResolveOutcome`, `DiscoverOutcome`, `ExecuteOutcome`  | Stable result wrappers returned by retrieval orchestration.                 |
| `RetrievalProviders` / `resolve_retrieval_providers()` | Dependency bundle and resolver for registry, profiles, tracer, and metrics. |

## Depends On / Depended On By

- Depends on: `polisyos.fabric.catalog`, `polisyos.fabric.connectors`,
  `polisyos.data_forge.read_api.catalog`, and
  `polisyos.core.contracts.control`.

- Depended on by: `polisyos.runtime.http.services.control` and any runtime or
  data-access flow that needs metric-driven fetch planning instead of direct
  connector calls.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg -n "RetrievalService|FetchExecutor|ExploreLaneDiscovery" src/polisyos/fabric/retrieval`
  Jump to the main retrieval entrypoints. Smoke-tested on 2026-04-17.

- `rg -n "FastLaneResolver|SourceBinding|MetricSearcher" src/polisyos/fabric/catalog src/polisyos/fabric/retrieval`
  Follow the boundary between retrieval and catalog resolution. Smoke-tested on
  2026-04-17.

- `rg -n "max_local_index_docs|max_promotion_candidates" src/polisyos/fabric/retrieval/service.py`
  Inspect the bounded-state controls for local indexing and promotion queues.
  Smoke-tested on 2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/test_retrieval_service_catalog.py -q`
  Retrieval service smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/test_data_catalog.py tests/unit/fabric/test_entity_resolution.py -q`
  Catalog and entity-resolution integration smoke suite. Smoke-tested on
  2026-04-17.

- `uv run pytest tests/unit/fabric -q`
  Full Fabric suite. Conceptual in this README refresh; not run in this pass.

## Reference Docs

- [Fabric reference index](../../../../docs/reference/fabric/index.md)
- [Fabric connectors reference](../../../../docs/reference/fabric/connectors.md)
- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Catalog README](../catalog/README.md)
- [Fabric tests map](../../../../tests/unit/fabric/README.md)
