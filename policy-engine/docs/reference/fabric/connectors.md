# Fabric Connectors

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `c35222b3dcf103338175cf300c5fe9487e6416f3`
Source plan: `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/connectors/**`, `src/polisyos/fabric/connectors/sources/**`, `tests/unit/fabric/connectors/**`, `pyproject.toml`
Evidence level: implementation and named connector-contract test behavior inspected at the source pin. Tests were not run in this documentation pass; live provider availability, source truth, and a connector-to-world/query chain are not established here.
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)
Inventory scope: code counts reflect statically resolved source declarations;
they do not prove runtime or deployment readiness. Dynamic or unresolved
declarations remain partial/unknown rather than being silently treated as absent.

The source package exports 20 concrete connector classes in
`polisyos.fabric.connectors.sources`. HTTP/open-data families share
`HTTPConnectorBase` for authentication, bounded fetches, retries, rate limiting,
circuit breaking, and normalized `FetchResult` construction. Non-HTTP expansion
families reuse the same protocol, schema, lineage, quality, and registry
contracts.

Connector capabilities are a hard runtime contract. Source profiles add planner
hints and transport preferences, but a profile does not imply that unsupported
async/schema methods exist on a connector family. These classes, profiles, and
contract checks describe adapter behavior and declared metadata. They do not
establish live source availability, scientific validity, or a downstream
world-fact/query consumer path.

## Protocol Contract

| Surface                           | Current contract                                                                                                                                                                                                                   |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Required class attributes         | Every connector class must declare `connector_id`, `capabilities`, and `metadata`.                                                                                                                                                 |
| Required async methods            | `connect()`, `disconnect()`, `health_check()`, and `fetch()` are mandatory for protocol compliance.                                                                                                                                |
| Capability-gated optional methods | `list_datasets()`, `fetch_stream()`, `check_freshness()`, `get_dataset_schema()`, `describe_dataset()`, `fetch_async()`, and `poll_async_fetch()` are only valid when the connector advertises the matching `ConnectorCapability`. |
| Runtime config boundary           | `ConnectionConfig` carries transport/auth/retry/rate-limit knobs only; planner-facing hints stay in `SourceExecutionPolicy`.                                                                                                       |
| Default behavior                  | `BaseConnector` raises `CapabilityError` or `NotImplementedError` when a class advertises a capability but leaves the default method in place.                                                                                     |

`tests/unit/fabric/connectors/test_protocol_compliance.py` is the executable source
for these rules. It checks missing attributes, missing async methods, metadata
capability drift, and the case where a connector advertises streaming but still
inherits `BaseConnector.fetch_stream()`.

## Connector Catalog

| Connector                | Source                                     | Protocol                                 | Auth                    | Example profile       | D1-L2 phase |
| ------------------------ | ------------------------------------------ | ---------------------------------------- | ----------------------- | --------------------- | ----------- |
| `WorldBankConnector`     | World Bank WDI                             | REST JSON                                | None                    | `worldbank_wdi`       | Phase 0/2   |
| `EurostatConnector`      | Eurostat                                   | REST JSON, SDMX, bulk export             | None                    | `eurostat_public`     | Phase 0/5   |
| `SDMXSourceConnector`    | ECB, OECD, IMF, BIS, ILO, FAO, UNSD        | SDMX REST                                | Profile-driven          | `oecd_sdmx`           | Phase 1/5   |
| `WHOConnector`           | WHO GHO                                    | REST JSON                                | None                    | `who_gho`             | Phase 5     |
| `UNPDConnector`          | UN Population Division                     | REST JSON                                | None                    | `unpd_dataportal`     | Phase 5     |
| `UNESCOUISConnector`     | UNESCO UIS                                 | REST JSON                                | None                    | `unesco_uis_public`   | Phase 5     |
| `WVSConnector`           | World Values Survey                        | REST JSON plus bulk-file profile support | None                    | `wvs_wave7`           | Phase 2/6   |
| `UKONSConnector`         | UK ONS                                     | REST JSON                                | None                    | `ukons_public`        | Phase 0/5   |
| `CKANCatalogConnector`   | CKAN package discovery                     | CKAN Action API                          | Profile-driven          | `data_gov_uk`         | Phase 0/5   |
| `CKANResourceConnector`  | CKAN resource download                     | CKAN metadata plus resource fetch        | Profile-driven          | `data_gov_us`         | Phase 0/5   |
| `SocrataConnector`       | Socrata portals                            | SODA / REST JSON                         | App token or none       | `nyc_opendata`        | Phase 0/2   |
| `OpendatasoftConnector`  | Opendatasoft hubs                          | Explore API v2.1                         | API key or none         | `paris_opendata`      | Phase 0/2   |
| `SPARQLConnector`        | Wikidata, DBpedia, similar KG endpoints    | SPARQL over HTTP                         | Usually none            | `wikidata_sparql`     | Phase 0/6   |
| `RestJsonConnector`      | Generic REST APIs                          | REST JSON                                | Configurable            | `open_meteo`          | Phase 0/5   |
| `FileTabularConnector`   | Local or remote CSV, JSONL, Parquet, Excel | File/HTTP object bytes                   | Path/profile-driven     | `files_demo_tabular`  | Phase 5     |
| `ObjectStorageConnector` | S3, GCS, Azure-style tabular objects       | Object URI plus file parser              | Provider/profile-driven | `object_storage_demo` | Phase 5     |
| `SQLQueryConnector`      | SQLite/DuckDB read-only query sources      | SQL                                      | Local/profile-driven    | `sqlite_demo`         | Phase 0/5   |
| `GraphQLConnector`       | Generic GraphQL APIs                       | GraphQL over HTTP                        | Header/profile-driven   | `graphql_demo`        | Phase 0/5   |
| `GeoJSONConnector`       | GeoJSON feature collections                | File/HTTP JSON                           | None/profile-driven     | `geojson_demo`        | Phase 5     |
| `EventStreamConnector`   | Newline-delimited JSON event streams       | JSONL stream/replay                      | None/profile-driven     | `stream_jsonl_demo`   | Phase 5     |

## Registration Status

| Surface                                            | Count | Detail                                                                                                                                                                                                                                                        |
| -------------------------------------------------- | ----: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Public names in source `__all__`                   |    24 | One `sources/__init__.py`: 20 `*Connector` classes, two shared HTTP types, `RawHTTPResponseObserver`, and `normalize_worldbank_records`                                                                                                                       |
| Concrete connector classes                         |    20 | `*Connector` exports from `polisyos.fabric.connectors.sources`, each resolved to a class in the source module                                                                                                                                                 |
| Built-in `SourceProfile` records                   |    38 | `SourceProfile(...)` declarations in the single `profiles/builtin_profiles.py` module; all profile ids are unique                                                                                                                                             |
| `pyproject` entry points                           |    11 | Entire `polisyos.fabric_connectors` table in one `pyproject.toml`: `worldbank.wdi`, `wvs.wave7`, `eurostat.data`, `ukons.datasets`, `sdmx.source`, `ckan.catalog`, `ckan.resource`, `socrata.soda`, `opendatasoft.ods`, `sparql.endpoint`, `rest.json`        |
| Built-in classes without a `pyproject` entry point |     9 | `WHOConnector`, `UNPDConnector`, `UNESCOUISConnector`, `FileTabularConnector`, `ObjectStorageConnector`, `SQLQueryConnector`, `GraphQLConnector`, `GeoJSONConnector`, and `EventStreamConnector` are included by `components.py`'s built-in component loader. |

These are declaration counts at the source pin: the complete export list in one
Python package initializer, all `SourceProfile(...)` calls in one Python module,
the full connector entry-point table in one TOML configuration file, and the
built-in class list in one Python component module. They describe code and
registration surfaces, not live-provider reachability or source truth.

## Phase Controls

| Phase   | Connector rule                                                                                                                                                                      |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0 | Build queries through safety helpers: identifiers, path segments, SPARQL/SoQL/ODSQL literals, REST/GraphQL data paths, and SQL table names must be validated before transport.      |
| Phase 1 | Connector registries, caches, pools, resilience wrappers, and background prefetch state must be locked, bounded, and deterministically closed.                                      |
| Phase 2 | `FetchResult.schema_id`, `schema_version`, `DataVersion`, units, numeric bounds, and transform outputs must be finite and semantically stable.                                      |
| Phase 3 | Connector changes that alter schema contracts must pass the schema-governance gate and emit impacted downstream surfaces when compatibility changes.                                |
| Phase 4 | Production connector metadata must carry owner, schema, quality-contract, SLA, access-classification, and retention-compatible governance fields.                                   |
| Phase 5 | New production-visible sources require SourceContract v2, profile compatibility, quality, replay or non-replayable reason, lineage seed, access, SLO, scorecard, and docs evidence. |

## Governance Metadata

`ConnectorMetadataSpec` now exposes structured views for Phase 4 governance:

| View                          | Fields                                                                                        |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `metadata.schema_governance`  | `schema_id`, `schema_id_template`, `schema_registry_ref`                                      |
| `metadata.quality_governance` | `quality_tier`, `quality_contract_id`, `quality_contract_ref`, finite-value requirement       |
| `metadata.operations.sla`     | availability target, freshness SLO, p95 latency target, replay-success target                 |
| `metadata.governance`         | owner, trust/quality tier, access classification, column classifications, quality contract id |

`validate_connector_governance_metadata()` is the executable metadata gate
used by the Phase 4 test suite. It checks the declared schema, quality, SLA,
access, and owner fields; passing it is not a live-provider readiness check or
proof of a complete connector-to-policy workflow. Phase 5 extends the declared
metadata criteria in [source-platform.md](source-platform.md).
`fabric.connectors.sdk` scaffolds SourceContract v2 authoring artifacts, and
`fabric.connectors.testing.conformance` validates protocol, profile, schema,
quality, replay, lineage, access, retention, and SLO evidence before a connector
is marked production-visible in the contract platform. That label reflects
those artifacts and checks, not current reachability or verified content from
the upstream provider.

## Schema Contracts And Compatibility

Connector schema truth is split across runtime contracts and committed
snapshots. The full compatibility policy, governance requirements, and
regeneration commands live in [schema-compatibility.md](schema-compatibility.md).

| Artifact                                                     | Source of truth                                                                       | Gate                                                                                                                      |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `schemas/snapshots/connectors/contracts.json`                | `polisyos.fabric.connectors.sources._contracts.ALL_SOURCE_CONTRACTS`                  | `uv run polisyos-tools connectors check-contracts --check`                                                                |
| `schemas/snapshots/fabric/connector_contract_registry.json`  | `tools/quality/validation/fabric_schema_governance.py` plus the same source contracts | `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json` |
| `schemas/snapshots/fabric/source_contracts_v2.json`          | `tools/quality/validation/fabric_source_contracts.py`                                 | `uv run python tools/quality/validation/fabric_source_contracts.py --check`                                               |
| `schemas/snapshots/fabric/{edge_kind,node_kind}.schema.json` | `src/polisyos/schemas/abi_models.py` and Fabric/world ABI models                      | `uv run --extra ml polisyos-tools diagnostics gen-schema --check`                                                         |

Breaking schema changes require an approved major bump, owner/reviewer
metadata, risk level, migration status, downstream impact summary, and migration
note. Compatible additions should produce a migration plan. The regression
coverage for this policy lives in `tests/repo_quality/tools/test_fabric_schema_governance.py`
and `tests/unit/fabric/connectors/test_contract_system.py`.

## Registry Tests

Use these as the documentation-linked registry checks before changing connector
registration or discovery behavior:

```bash
uv run pytest tests/unit/fabric/connectors/test_registry.py -q
uv run pytest tests/unit/fabric/connectors/sources/test_connector_family_expansion.py -q
uv run pytest tests/unit/fabric/connectors/test_protocol_compliance.py -q
uv run pytest tests/unit/fabric/connectors/test_contract_system.py tests/repo_quality/tools/test_fabric_schema_governance.py -q
```

## Shared HTTP Base

| API                     | Role                                                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `HTTPResilienceProfile` | Source-specific retry, backoff, and circuit-breaker defaults                                                       |
| `HTTPConnectorBase`     | Shared authenticated HTTP runtime, bounded response handling, resilience wrapping, and `FetchResult` normalization |

## API Reference

::: polisyos.fabric.connectors.base

::: polisyos.fabric.connectors.capabilities

::: polisyos.fabric.connectors.sources.http_base

::: polisyos.fabric.connectors.sources.world_bank

::: polisyos.fabric.connectors.sources.eurostat

::: polisyos.fabric.connectors.sources.sdmx_source

::: polisyos.fabric.connectors.sources.who

::: polisyos.fabric.connectors.sources.unpd

::: polisyos.fabric.connectors.sources.unesco_uis

::: polisyos.fabric.connectors.sources.wvs

::: polisyos.fabric.connectors.sources.ukons

::: polisyos.fabric.connectors.sources.ckan_catalog

::: polisyos.fabric.connectors.sources.ckan_resource

::: polisyos.fabric.connectors.sources.socrata

::: polisyos.fabric.connectors.sources.opendatasoft

::: polisyos.fabric.connectors.sources.sparql

::: polisyos.fabric.connectors.sources.rest_json

::: polisyos.fabric.connectors.sources.file_tabular

::: polisyos.fabric.connectors.sources.object_storage

::: polisyos.fabric.connectors.sources.sql_query

::: polisyos.fabric.connectors.sources.graphql_api

::: polisyos.fabric.connectors.sources.geojson

::: polisyos.fabric.connectors.sources.event_stream
