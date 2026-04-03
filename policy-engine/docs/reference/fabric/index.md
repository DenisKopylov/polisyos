# Fabric
Related explanation: [Data Fabric](../../explanation/data-fabric.md).

> Data acquisition and world-materialization layer for PolicyOS.

`polisyos.fabric` normalizes external data access behind connector contracts, source profiles,
document/claim normalization stages, and data-plane orchestration. It powers both direct world
queries over materialized tables and reproducible ingestion flows that persist evidence,
provenance, and conflict-resolution artifacts into CAS.

## Current Surface

| Area | Current code status | Reference |
|------|---------------------|-----------|
| Connector classes | 14 concrete connector classes exported from `connectors.sources` | [connectors.md](connectors.md) |
| Entry-point registrations | 11 connector entry points currently declared in `pyproject.toml` | [connectors.md](connectors.md) |
| Built-in profiles | 32 builtin `SourceProfile` instances across 13 connector families | [profiles.md](profiles.md) |
| Data plane | Orchestrator, execution modes, watermark policy, docs/claims/world-query semantics | [data-plane.md](data-plane.md) |

## Root API

| Export | Role |
|--------|------|
| `fabric_get_data` | Compatibility bridge for connector-backed fetches |
| `run_connectors_ingestion` | Execute ingestion over a connector manifest |
| `execute_world_query` | Run a world query against Fabric materializations |
| `query_claims` / `query_events` / `query_world_table` | Query convenience helpers for world storage |
| `WorldQueryRequest` / `WorldQueryError` | Request and error surface for world querying |
| `world` | Lazy-loaded `polisyos.fabric.world` module |

## Catalog Surface

Fabric also lazy-loads contract and search types from `polisyos.fabric.catalog`, including `DataContract`, `DataContractCollection`, `DataContractRegistry`, `MetricSearcher`, `SearchResult`, and `load_contract_collection`.

## Notes

| Item | Detail |
|------|--------|
| Concrete vs entry-point connectors | `WHOConnector`, `UNPDConnector`, and `UNESCOUISConnector` are concrete exported classes today, but they are not yet wired into the `polisyos.fabric_connectors` entry-point section in `pyproject.toml` |
| Profile counts | The current `builtin_profiles.py` defines 32 profiles. This diverges from earlier planning notes that mentioned 63 |
| Bindings location | Fabric’s deprecated bindings live under `connectors/bindings/`; the active multiscale binding logic referenced elsewhere lives in Foundry, not under `polisyos.fabric.data_plane.bindings` |
