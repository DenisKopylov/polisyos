# Retrieval (`polisyos.fabric.retrieval`)

`polisyos.fabric.retrieval` turns a `DataNeed` into deterministic resolution,
bounded live discovery, executable fetch plans, previews, and promotion
signals.

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
  `polisyos.datasets.batch.source_registry`, and
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

- `uv run pytest tests/fabric/test_retrieval_service_catalog.py -q`
  Retrieval service smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/fabric/test_data_catalog.py tests/fabric/test_entity_resolution.py -q`
  Catalog and entity-resolution integration smoke suite. Smoke-tested on
  2026-04-17.

- `uv run pytest tests/fabric -q`
  Full Fabric suite. Conceptual in this README refresh; not run in this pass.

## Reference Docs

- [Fabric reference index](../../../../docs/reference/fabric/index.md)
- [Fabric connectors reference](../../../../docs/reference/fabric/connectors.md)
- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Catalog README](../catalog/README.md)
- [Fabric tests map](../../../../tests/fabric/README.md)
