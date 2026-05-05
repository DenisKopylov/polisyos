# Fabric (`polisyos.fabric`)

`polisyos.fabric` is the repository's data-fabric layer: connector-backed
acquisition, document and claim pipelines, data-plane orchestration,
provenance, retrieval, and world materialization.

- Last updated: 2026-04-17

## Purpose

Use `polisyos.fabric` when you need to move from external data or documents to
deterministic CAS artifacts, lineage, claims, and queryable world state. The
root package exposes the stable facade used by higher layers, while the
subpackage READMEs below explain the implementation boundaries in more detail.

## Where to Start

- Start with [connectors/README.md](./connectors/README.md) when adding,
  registering, validating, or debugging a data source.

- Start with [data_plane/README.md](./data_plane/README.md) for batch, record,
  replay, streaming, CDC, quarantine, and semantic-diff flows.

- Start with [docs/README.md](./docs/README.md),
  [claims/README.md](./claims/README.md), and [world/README.md](./world/README.md)
  for the document-to-world pipeline.

- Start with [retrieval/README.md](./retrieval/README.md) and
  [catalog/README.md](./catalog/README.md) for metric discovery, fetch planning,
  and semantic catalog behavior.

- Use [tests/unit/fabric/README.md](../../../tests/unit/fabric/README.md) to find the
  focused validation suite for the area you are changing.

## Public Entrypoints

| Entrypoint                              | Description                                                                                       |
| --------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `run_connectors_ingestion()`            | Main ingestion entrypoint for connector-backed runs.                                              |
| `fabric_get_data()`                     | Compatibility bridge used by upper layers that need synchronous fetch access.                     |
| `execute_world_query()`                 | Read-only world-query entrypoint over Fabric materializations.                                    |
| `query_world_table()`                   | Convenience helper for direct world-table reads.                                                  |
| `query_claims()` / `query_events()`     | Helpers for claim and world-event query paths.                                                    |
| `WorldQueryRequest` / `WorldQueryError` | Request and error surface for governed world queries.                                             |
| `world`                                 | Lazy-loaded `polisyos.fabric.world` subpackage for lower-level write and materialization helpers. |

`polisyos.fabric.__all__` is the stable public facade. Catalog and semantic
discovery surfaces live under `polisyos.fabric.catalog` and are linked from the
retrieval README rather than being part of the root facade contract.

## Depends On / Depended On By

- Depends on: `polisyos.common`, `polisyos.core`, `polisyos.ir`,
  `polisyos.data_forge.read_api.catalog`, and the Fabric subpackages
  documented here.

- Depended on by: `polisyos.runtime.http.services.control`,
  `polisyos.scientist`, `polisyos.scholar`, `polisyos.lex`, and any code that
  reads materialized world state or connector-backed data contexts.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg --files src/polisyos/fabric | sort`
  Survey the package map before following imports. Smoke-tested on 2026-04-17.

- `rg -n "run_connectors_ingestion\|fabric_get_data\|execute_world_query" src/polisyos/fabric`
  Jump to the root facade and bridging entrypoints. Smoke-tested on 2026-04-17.

- `uv run python -m polisyos.fabric.data_plane.cli --help`
  Inspect the package-local quarantine/report CLI exposed inside Fabric.
  Smoke-tested on 2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/test_docs_pipeline.py tests/unit/fabric/test_claims_pipeline.py tests/unit/fabric/test_retrieval_service_catalog.py tests/unit/fabric/test_world_store.py -q`
  Cross-package Fabric smoke suite. Smoke-tested on 2026-04-17.

- `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json`
  Connector contract compatibility gate. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric -q`
  Full Fabric suite. Conceptual in this README refresh; not run in this pass.

## Reference Docs

- [Fabric reference index](../../../docs/reference/fabric/index.md)
- [Fabric connectors reference](../../../docs/reference/fabric/connectors.md)
- [Fabric data-plane reference](../../../docs/reference/fabric/data-plane.md)
- [Fabric lineage reference](../../../docs/reference/fabric/lineage.md)
- [Connector CONTRIBUTING guide](../../../docs/connectors/CONTRIBUTING.md)
- [Add data source](../../../docs/how-to/add-data-source.md)
- [Manage generated artifacts](../../../docs/how-to/manage-generated-artifacts.md)
- [Fabric tests map](../../../tests/unit/fabric/README.md)
