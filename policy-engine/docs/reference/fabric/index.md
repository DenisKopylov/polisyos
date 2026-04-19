# Fabric

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

> Data acquisition, connector governance, lineage, and world-materialization
> layer for PolicyOS.

Freshness: 2026-04-17.
Owner: `@fabric-owners`
Source plan: `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/**`, `tests/fabric/**`, `schemas/snapshots/{fabric,connectors}/**`, `tools/quality/validation/fabric_schema_governance.py`

`polisyos.fabric` normalizes external data access behind connector contracts,
source profiles, document/claim normalization stages, retrieval, data-plane
orchestration, and world materialization. It powers reproducible ingestion flows
that persist evidence, provenance, quarantine records, CDC events, and
conflict-resolution artifacts into CAS before downstream Scientist, Scholar, or
Lex code consumes them.

## Current Surface

| Area | Current code status | Reference |
|---|---|---|
| Connector classes | 20 concrete connector classes exported from `polisyos.fabric.connectors.sources` | [connectors.md](connectors.md) |
| Entry-point registrations | 11 connector entry points declared in `pyproject.toml` for the production HTTP/open-data families | [connectors.md](connectors.md#registration-status) |
| Built-in profiles | 38 built-in `SourceProfile` instances across 19 connector families | [profiles.md](profiles.md) |
| Data plane | Orchestrator, batch/record/replay/streaming modes, cursor state, quarantine, CDC events, semantic diff, and benchmarks | [data-plane.md](data-plane.md) |
| Schema governance | `DataSchema`, `SchemaEvolution`, contract governance metadata, and committed connector-contract snapshots with CI evidence | [schema-compatibility.md](schema-compatibility.md) |
| Lineage | `FabricLineageTracker`, trace APIs, impact analysis, OpenLineage export, and visualization graph export | [lineage.md](lineage.md) |
| Quality | Metric-level quality indicators, dataset-level validation, drift/anomaly profiling, and `DataFitnessReport` summaries | [quality.md](quality.md) |
| Time travel | Bitemporal world queries, retained DuckDB snapshots, logical branches, merge policies, and retention/GC | [time-travel.md](time-travel.md) |

## Page Map

| Page | Scope | Primary modules | Validation anchor |
|---|---|---|---|
| [connectors.md](connectors.md) | Connector protocol, runtime classes, discovery/registration, connector families | `fabric.connectors.base`, `fabric.connectors.capabilities`, `fabric.connectors.sources.*` | `tests/fabric/connectors/test_protocol_compliance.py`, `tests/fabric/connectors/test_registry.py` |
| [profiles.md](profiles.md) | `SourceProfile`, `SourceExecutionPolicy`, registry, planner/runtime normalization | `fabric.connectors.profiles.*` | `tests/fabric/connectors/profiles/test_source_profiles.py` |
| [data-plane.md](data-plane.md) | Ingestion orchestration, modes, cursor store, quarantine, streaming, semantic diff | `fabric.data_plane.*`, `fabric.world_query` | `tests/fabric/data_plane/test_orchestrator.py`, `tests/fabric/data_plane/test_streaming_runtime.py` |
| [schema-compatibility.md](schema-compatibility.md) | Connector contracts, schema diffing, migration plans, governance evidence, snapshot gates | `fabric.connectors.contracts.*`, `tools/quality/validation/fabric_schema_governance.py` | `tests/fabric/connectors/test_schema_system.py`, `tests/tools/test_fabric_schema_governance.py` |
| [lineage.md](lineage.md) | Source-to-query lineage graph, trace helpers, impact analysis, export formats | `fabric.provenance.lineage`, `fabric.observability` | `tests/fabric/test_lineage.py`, `tests/fabric/test_fabric_observability.py` |
| [quality.md](quality.md) | Quality indicators, validator stack, drift/anomaly stats, evidence/fitness reports | `fabric.quality`, `fabric.fitness_report`, `fabric.connectors.quality.*` | `tests/fabric/test_quality_indicators.py`, `tests/fabric/connectors/test_quality_system.py` |
| [time-travel.md](time-travel.md) | Snapshot retention, branch merge, adapter limits, bitemporal query semantics | `fabric.world.store.snapshots`, `fabric.world_query` | `tests/fabric/test_world_time_travel.py`, `tests/fabric/test_world_materialization.py` |

## D1-L2 Source-Of-Truth Map

The canonical source plan is `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`. This
reference page maps that plan to the documentation surface that should stay in
sync with code, tests, and generated artifacts.

| Source phase | Current source-of-truth surface | Docs surface |
|---|---|---|
| Phase 0: query/filter injection, bounded input, serialization/provenance, UTC temporal policy | `polisyos.fabric.safety`, HTTP/source connectors, `quality.py`, `fitness_report.py`, `provenance/export_provo.py`, `temporal.py`; tests under `tests/fabric/connectors/sources/`, `tests/fabric/test_quality_indicators.py`, `tests/fabric/test_provenance.py` | [connectors.md](connectors.md), [add-data-source](../../how-to/add-data-source.md), package READMEs |
| Phase 1: deterministic lifecycle, atomic persistence, contention resilience, mutable state, bounded memory | connector registry/pool/cache/resilience, `data_plane/cursor_store.py`, `world/store/segments.py`, retrieval bounded queues; tests under `tests/fabric/connectors/test_{cache_system,resilience,registry}.py`, `tests/fabric/data_plane/` | [connectors.md](connectors.md), [profiles.md](profiles.md), [cache runbook](../../runbooks/cache-rebuild-storm.md) |
| Phase 2: schema merge, numeric quality bounds, units, canonical IDs, transform correctness | connector contracts, schema evolution, type/unit registries, transform pipeline, quality finite checks; tests under `tests/fabric/connectors/test_{contract_system,schema_system,type_system,transform_pipeline}.py` | [connectors.md](connectors.md#schema-contracts-and-compatibility), [profiles.md](profiles.md), [manage-generated-artifacts](../../how-to/manage-generated-artifacts.md) |
| Phase 3: observability/SLO, lineage, schema compatibility, access control, retention | `observability.py`, `provenance/lineage.py`, `security/*`, `tools/quality/validation/fabric_schema_governance.py`, `schemas/snapshots/fabric/connector_contract_registry.json`; tests under `tests/fabric/test_{fabric_observability,lineage,access_control}.py`, `tests/tools/test_fabric_schema_governance.py` | [lineage.md](lineage.md), [schema-compatibility.md](schema-compatibility.md), [manage-generated-artifacts](../../how-to/manage-generated-artifacts.md), recovery runbooks |
| Phase 4: quality profiling, materialization, time travel | connector quality statistics, `data_plane/semantic_diff.py`, `world/materialize/*`, `world_query.py`; tests under `tests/fabric/test_{quality_indicators,world_materialization,world_time_travel,semantic_diff}.py` | [quality.md](quality.md), [time-travel.md](time-travel.md), [data-plane.md](data-plane.md), `src/polisyos/fabric/world/README.md` |
| Phase 5: DLQ/quarantine, connector ecosystem, streaming/CDC, scale-out | `data_plane/quarantine.py`, `data_plane/streaming.py`, file/object/SQL/GraphQL/GeoJSON/stream connector families, benchmarks; tests under `tests/fabric/data_plane/test_{quarantine,streaming_runtime,scale_out,benchmarks}.py`, `tests/fabric/connectors/sources/test_connector_family_expansion.py` | [connectors.md](connectors.md#connector-catalog), [data-plane.md](data-plane.md#execution-modes), [add-data-source](../../how-to/add-data-source.md), [Fabric quarantine/DLQ runbook](../../runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md) |
| Phase 6: semantic catalog, natural-language discovery, entity resolution | `catalog/{semantic,search,source_bindings}.py`, `retrieval/*`, `entity_resolution/*`; tests under `tests/fabric/test_{data_catalog,retrieval_service_catalog,entity_resolution}.py` | `src/polisyos/fabric/retrieval/README.md`, `src/polisyos/fabric/world/README.md`, future catalog reference |

## Documentation Impact

| Output cluster | Exact files | Source of truth | Validation |
|---|---|---|---|
| Reference set | `docs/reference/fabric/index.md`, `docs/reference/fabric/connectors.md`, `docs/reference/fabric/profiles.md`, `docs/reference/fabric/data-plane.md`, `docs/reference/fabric/schema-compatibility.md`, `docs/reference/fabric/lineage.md`, `docs/reference/fabric/quality.md`, `docs/reference/fabric/time-travel.md` | connector registry, built-in profiles, connector contracts, lineage/quality modules, data-plane/runtime schema snapshots, world snapshot/query modules | `uv run pytest tests/fabric/connectors/test_registry.py tests/fabric/connectors/test_protocol_compliance.py tests/fabric/connectors/test_contract_system.py tests/fabric/connectors/test_schema_system.py tests/fabric/test_lineage.py tests/fabric/test_quality_indicators.py tests/fabric/test_world_time_travel.py -q` |
| Authoring and generated-artifact guidance | `docs/connectors/CONTRIBUTING.md`, `docs/how-to/add-data-source.md`, `docs/how-to/manage-generated-artifacts.md` | connector scaffolding rules, profile/contracts registry, snapshot governance tooling | `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out .tmp/fabric-schema-governance.json` |
| Recovery runbooks | `docs/runbooks/cache-rebuild-storm.md`, `docs/runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md`, `docs/runbooks/retained-artifact-recovery.md`, `docs/runbooks/artifact-corruption-recovery.md` | cache/index lifecycle, quarantine/DLQ replay, streaming checkpoint recovery, CAS-backed artifact retention and restore paths, corruption detection flows | `uv run pytest tests/fabric/data_plane/test_quarantine.py tests/fabric/data_plane/test_streaming_runtime.py tests/fabric/test_lineage.py -q` |
| Package boundary READMEs | `src/polisyos/fabric/README.md`, `src/polisyos/fabric/connectors/README.md`, `src/polisyos/fabric/data_plane/README.md`, `src/polisyos/fabric/retrieval/README.md`, `src/polisyos/fabric/world/README.md` | package facades, connector families, data-plane modes, retrieval/catalog entry points, world materialization boundary | `uv run pytest tests/fabric -q` |

## Root API

| Export | Role |
|---|---|
| `fabric_get_data` | Compatibility bridge for connector-backed fetches |
| `run_connectors_ingestion` | Execute ingestion over a connector manifest |
| `execute_world_query` | Run a governed read-only world query against Fabric materializations |
| `query_claims` / `query_events` / `query_world_table` | Query convenience helpers for world storage |
| `WorldQueryRequest` / `WorldQueryError` | Request and error surface for world querying |
| `world` | Lazy-loaded `polisyos.fabric.world` module |

Fabric also lazy-loads catalog types such as `DataContract`,
`DataContractCollection`, `DataContractRegistry`, `MetricSearcher`,
`SearchResult`, and `load_contract_collection` through `__getattr__`.

## Validation Anchors

| Validation | Command or test |
|---|---|
| Connector registry behavior | `uv run pytest tests/fabric/connectors/test_registry.py -q` |
| Connector contract/runtime schema behavior | `uv run pytest tests/fabric/connectors/test_contract_system.py tests/fabric/connectors/test_schema_system.py -q` |
| Schema compatibility governance gate | `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out .tmp/fabric-schema-governance.json` |
| Legacy connector contract snapshot gate | `uv run python tools/connectors/check_contracts.py --check` |
| Fabric ABI snapshot gate | `uv run --extra ml polisyos-tools diagnostics gen-schema --check` |
| Quality and lineage examples | `uv run pytest tests/fabric/test_quality_indicators.py tests/fabric/test_lineage.py -q` |
| Quarantine and streaming/CDC examples | `uv run pytest tests/fabric/data_plane/test_quarantine.py tests/fabric/data_plane/test_streaming_runtime.py -q` |

## Notes

| Item | Detail |
|---|---|
| Concrete vs entry-point connectors | `polisyos.fabric.connectors.sources.__all__` currently exports 22 names: 20 concrete connector classes plus `HTTPConnectorBase` and `HTTPResilienceProfile`. The `polisyos.fabric_connectors` entry-point section exposes 11 production HTTP/open-data components; the file, object-storage, SQL, GraphQL, GeoJSON, stream, WHO, UNPD, and UNESCO UIS families are available by direct import or registry wiring but are not all entry-point registered. |
| Profile counts | `src/polisyos/fabric/connectors/profiles/builtin_profiles.py` currently defines 38 profiles. Earlier planning notes that mention 63 profiles are future-state, not this workspace state. |
| Bindings location | Deprecated connector bindings live under `connectors/bindings/`; active multiscale binding logic referenced by other lanes belongs to Foundry, not `polisyos.fabric.data_plane.bindings`. |
| Current artifacts | Current connector compatibility snapshots are `schemas/snapshots/fabric/connector_contract_registry.json` and `schemas/snapshots/connectors/contracts.json`, each with 5 committed contracts: `eurostat.data.generic`, `sdmx.generic`, `ukons.datasets.generic`, `worldbank.wdi.generic`, and `wvs.wave7.generic`. Fabric ABI snapshots remain `schemas/snapshots/fabric/{edge_kind,node_kind}.schema.json`. |

## Backlog

| Gap | Priority | Tracking note |
|---|---|---|
| No missing required D2-L2 reference pages | - | Connector protocol, source profiles, data-plane, schema compatibility, lineage, quality, and time-travel pages are present and mapped above. |
| Standalone semantic-catalog reference page | P2 | The current L2 D2 scope still documents catalog behavior through `retrieval/README.md`, `world/README.md`, and the Fabric reference set. A dedicated catalog page remains a follow-on expansion. |
